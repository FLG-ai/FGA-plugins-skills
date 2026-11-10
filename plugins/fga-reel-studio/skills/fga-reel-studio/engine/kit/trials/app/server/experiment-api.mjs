import { copyFile, mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { requestZernio } from "./zernio-api.mjs";

// Test history lives outside the app folder, so replacing or updating the app never touches it.
// Inside Reel Kit it sits in the kit's home (REEL_KIT_HOME, default ~/reel-kit), next to the key in .env.
const KIT_HOME = (process.env.REEL_KIT_HOME || "").replace(/^~(?=$|\/)/, homedir()) || join(homedir(), "reel-kit");
export const DATA_DIR = process.env.TRIALS_DATA_DIR || join(KIT_HOME, "trials");
const DEFAULT_FILE = join(DATA_DIR, "experiments.json");
// Where history lived before it moved out. Copied over once, never deleted.
const LEGACY_FILE = fileURLToPath(new URL("../data/experiments.json", import.meta.url));
const BACKUPS_KEPT = 30;
const METRICS = [
  "views",
  "reach",
  "impressions",
  "likes",
  "comments",
  "shares",
  "saves",
  "engagementRate",
  "igReelsAvgWatchTime",
  "igReelsVideoViewTotalTime",
  "reelsSkipRate",
];

function sendJson(response, status, payload) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(payload));
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 1_000_000) throw new Error("Request body is too large.");
    chunks.push(chunk);
  }
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
}

function cleanText(value, maxLength) {
  return String(value || "").trim().slice(0, maxLength);
}

function normalizeAnalytics(data) {
  const instagram = data.platformAnalytics?.find((entry) => entry.platform === "instagram") || data.platformAnalytics?.[0] || {};
  const source = instagram.analytics || data.analytics || {};
  const analytics = {};
  for (const metric of METRICS) analytics[metric] = Number(source[metric] || 0);

  return {
    analytics,
    status: instagram.status || data.status || "published",
    platformPostId: instagram.platformPostId || null,
    platformPostUrl: instagram.platformPostUrl || data.platformPostUrl || null,
    publishedAt: data.publishedAt || null,
    syncStatus: instagram.syncStatus || data.syncStatus || "pending",
    analyticsUpdatedAt: source.lastUpdated || new Date().toISOString(),
  };
}

const LIVE = ["published", "success", "completed"];

function postState(post) {
  const target = post?.platforms?.find((entry) => entry.platform === "instagram") || post?.platforms?.[0] || {};
  const raw = target.status || post?.status || "processing";
  return {
    status: LIVE.includes(raw) ? "published" : ["failed", "error", "cancelled"].includes(raw) ? "failed" : raw,
    url: target.platformPostUrl || post?.platformPostUrl || null,
    platformPostId: target.platformPostId || null,
    publishedAt: target.publishedAt || post?.publishedAt || null,
    error: target.errorMessage || target.error || null,
  };
}

export function createExperimentApi({ filePath = DEFAULT_FILE, legacyFile = filePath === DEFAULT_FILE ? LEGACY_FILE : null } = {}) {
  let updateQueue = Promise.resolve();
  const backupDir = join(dirname(filePath), "backups");

  async function readData() {
    if (legacyFile && !existsSync(filePath) && existsSync(legacyFile)) {
      await mkdir(dirname(filePath), { recursive: true });
      await copyFile(legacyFile, filePath);
    }
    try {
      const parsed = JSON.parse(await readFile(filePath, "utf8"));
      return { version: 1, experiments: Array.isArray(parsed.experiments) ? parsed.experiments : [] };
    } catch (error) {
      if (error.code === "ENOENT") return { version: 1, experiments: [] };
      throw error;
    }
  }

  // Before the first change each day, keeps a copy of the file as it was. The newest 30 days stay.
  async function backUp() {
    if (!existsSync(filePath)) return;
    await mkdir(backupDir, { recursive: true });
    const today = join(backupDir, `experiments-${new Date().toISOString().slice(0, 10)}.json`);
    if (existsSync(today)) return;
    await copyFile(filePath, today);
    const old = (await readdir(backupDir)).filter((name) => /^experiments-\d{4}-\d{2}-\d{2}\.json$/.test(name)).sort().slice(0, -BACKUPS_KEPT);
    await Promise.all(old.map((name) => rm(join(backupDir, name))));
  }

  async function writeData(data) {
    await mkdir(dirname(filePath), { recursive: true });
    await backUp();
    const temporaryPath = `${filePath}.tmp`;
    await writeFile(temporaryPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
    await rename(temporaryPath, filePath);
  }

  function updateData(updater) {
    const operation = updateQueue.then(async () => {
      const data = await readData();
      const result = await updater(data);
      await writeData(data);
      return result;
    });
    updateQueue = operation.catch(() => {});
    return operation;
  }

  async function handle(request, response, apiKey) {
    const url = new URL(request.url, "http://trialr.local");
    if (!url.pathname.startsWith("/api/experiments")) return false;

    try {
      if (url.pathname === "/api/experiments" && request.method === "GET") {
        const data = await readData();
        const experiments = [...data.experiments].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
        sendJson(response, 200, { experiments });
        return true;
      }

      if (url.pathname === "/api/experiments" && request.method === "POST") {
        const body = await readJson(request);
        const name = cleanText(body.name, 100);
        if (!name) {
          sendJson(response, 400, { error: "Experiment name is required." });
          return true;
        }

        const experiment = {
          id: crypto.randomUUID(),
          name,
          hypothesis: cleanText(body.hypothesis, 240),
          caption: cleanText(body.caption, 2200),
          primaryMetric: METRICS.includes(body.primaryMetric) ? body.primaryMetric : "views",
          status: "active",
          createdAt: new Date().toISOString(),
          variants: [],
        };
        await updateData((data) => data.experiments.push(experiment));
        sendJson(response, 201, { experiment });
        return true;
      }

      const variantMatch = url.pathname.match(/^\/api\/experiments\/([^/]+)\/variants$/);
      if (variantMatch && request.method === "POST") {
        const body = await readJson(request);
        const label = cleanText(body.label, 120);
        if (!label || !body.zernioPostId) {
          sendJson(response, 400, { error: "label and zernioPostId are required." });
          return true;
        }

        const variant = {
          id: crypto.randomUUID(),
          label,
          originalFilename: cleanText(body.originalFilename, 240),
          zernioPostId: cleanText(body.zernioPostId, 160),
          platformPostId: cleanText(body.platformPostId, 160) || null,
          platformPostUrl: cleanText(body.platformPostUrl, 1000) || null,
          mediaUrl: cleanText(body.mediaUrl, 2000) || null,
          thumbnail: cleanText(body.thumbnail, 500_000) || null,
          status: cleanText(body.status, 40) || "processing",
          publishedAt: body.publishedAt || new Date().toISOString(),
          createdAt: new Date().toISOString(),
          analytics: null,
          syncStatus: "pending",
          analyticsUpdatedAt: null,
          analyticsSnapshots: [],
        };

        const result = await updateData((data) => {
          const experiment = data.experiments.find((entry) => entry.id === variantMatch[1]);
          if (!experiment) return null;
          experiment.variants.push(variant);
          return experiment;
        });
        if (!result) {
          sendJson(response, 404, { error: "Experiment not found." });
          return true;
        }
        sendJson(response, 201, { variant, experiment: result });
        return true;
      }

      const testMatch = url.pathname.match(/^\/api\/experiments\/([^/]+)$/);
      if (testMatch && request.method === "PATCH") {
        const body = await readJson(request);
        const hasWinner = "winnerId" in body;
        const hasName = "name" in body;
        if (!hasWinner && !hasName) {
          sendJson(response, 400, { error: "Send a name or a winnerId (null clears the winner)." });
          return true;
        }
        const name = hasName ? cleanText(body.name, 100) : "";
        if (hasName && !name) {
          sendJson(response, 400, { error: "Test name can't be empty." });
          return true;
        }
        const winnerId = hasWinner && body.winnerId !== null ? cleanText(body.winnerId, 80) : null;
        let missingVariant = false;
        const result = await updateData((data) => {
          const experiment = data.experiments.find((entry) => entry.id === testMatch[1]);
          if (!experiment) return null;
          if (winnerId && !experiment.variants.some((variant) => variant.id === winnerId)) {
            missingVariant = true;
            return null;
          }
          if (hasName) experiment.name = name;
          if (hasWinner) {
            experiment.winnerId = winnerId;
            experiment.decidedAt = winnerId ? new Date().toISOString() : null;
          }
          return experiment;
        });
        if (!result) {
          sendJson(response, missingVariant ? 400 : 404, { error: missingVariant ? "That version isn't in this test." : "Experiment not found." });
          return true;
        }
        sendJson(response, 200, { experiment: result });
        return true;
      }

      // Deleting only touches the local record. The posts stay live on Instagram.
      if (testMatch && request.method === "DELETE") {
        const removed = await updateData((data) => {
          const index = data.experiments.findIndex((entry) => entry.id === testMatch[1]);
          if (index < 0) return false;
          data.experiments.splice(index, 1);
          return true;
        });
        if (!removed) {
          sendJson(response, 404, { error: "Experiment not found." });
          return true;
        }
        sendJson(response, 200, { deleted: testMatch[1] });
        return true;
      }

      const renameMatch = url.pathname.match(/^\/api\/experiments\/([^/]+)\/variants\/([^/]+)$/);
      if (renameMatch && request.method === "PATCH") {
        const body = await readJson(request);
        const label = cleanText(body.label, 120);
        if (!label) {
          sendJson(response, 400, { error: "label is required." });
          return true;
        }
        const result = await updateData((data) => {
          const experiment = data.experiments.find((entry) => entry.id === renameMatch[1]);
          const variant = experiment?.variants.find((entry) => entry.id === renameMatch[2]);
          if (!variant) return null;
          variant.label = label;
          return experiment;
        });
        if (!result) {
          sendJson(response, 404, { error: "Version not found." });
          return true;
        }
        sendJson(response, 200, { experiment: result });
        return true;
      }

      if (renameMatch && request.method === "DELETE") {
        const result = await updateData((data) => {
          const experiment = data.experiments.find((entry) => entry.id === renameMatch[1]);
          const index = experiment ? experiment.variants.findIndex((entry) => entry.id === renameMatch[2]) : -1;
          if (index < 0) return null;
          experiment.variants.splice(index, 1);
          if (experiment.winnerId === renameMatch[2]) {
            experiment.winnerId = null;
            experiment.decidedAt = null;
          }
          return experiment;
        });
        if (!result) {
          sendJson(response, 404, { error: "Version not found." });
          return true;
        }
        sendJson(response, 200, { experiment: result });
        return true;
      }

      const refreshMatch = url.pathname.match(/^\/api\/experiments\/([^/]+)\/refresh$/);
      if (refreshMatch && request.method === "POST") {
        if (!apiKey) {
          sendJson(response, 503, { error: "Zernio is not configured." });
          return true;
        }
        const current = await readData();
        const experiment = current.experiments.find((entry) => entry.id === refreshMatch[1]);
        if (!experiment) {
          sendJson(response, 404, { error: "Experiment not found." });
          return true;
        }

        const refreshed = [];
        const failures = [];
        for (const variant of experiment.variants) {
          try {
            // A scheduled version has nothing to measure until Zernio posts it. Check that first.
            if (!LIVE.includes(variant.status)) {
              const postData = await requestZernio(apiKey, `/posts/${encodeURIComponent(variant.zernioPostId)}`);
              const state = postState(postData.post || postData);
              if (!LIVE.includes(state.status)) {
                refreshed.push({ variantId: variant.id, status: state.status === "failed" ? "failed" : variant.status, ...(state.error ? { error: state.error } : {}) });
                continue;
              }
              refreshed.push({ variantId: variant.id, status: "published", platformPostId: state.platformPostId, platformPostUrl: state.url, publishedAt: state.publishedAt || variant.publishedAt });
            }
            const analyticsData = await requestZernio(apiKey, `/analytics?postId=${encodeURIComponent(variant.zernioPostId)}`);
            refreshed.push({ variantId: variant.id, ...normalizeAnalytics(analyticsData) });
          } catch (error) {
            failures.push({ variantId: variant.id, error: error.message });
          }
        }

        const updated = await updateData((data) => {
          const target = data.experiments.find((entry) => entry.id === refreshMatch[1]);
          if (!target) return null;
          for (const result of refreshed) {
            const variant = target.variants.find((entry) => entry.id === result.variantId);
            if (!variant) continue;
            const { variantId, ...fields } = result;
            Object.assign(variant, fields);
            if (!fields.analytics) continue;
            const capturedAt = new Date().toISOString();
            variant.lastRefreshedAt = capturedAt;
            variant.analyticsSnapshots = [...(variant.analyticsSnapshots || []), { capturedAt, analytics: fields.analytics }].slice(-20);
          }
          return target;
        });
        sendJson(response, failures.length && !refreshed.length ? 424 : 200, { experiment: updated, failures });
        return true;
      }

      sendJson(response, 404, { error: "Experiment API route not found." });
      return true;
    } catch (error) {
      sendJson(response, 500, { error: error.message || "Experiment request failed." });
      return true;
    }
  }

  return { handle, readData };
}

export const experimentApi = createExperimentApi();

export function handleExperimentApi(request, response, apiKey) {
  return experimentApi.handle(request, response, apiKey);
}
