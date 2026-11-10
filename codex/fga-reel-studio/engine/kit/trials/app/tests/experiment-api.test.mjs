import assert from "node:assert/strict";
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import test from "node:test";
import { createExperimentApi } from "../server/experiment-api.mjs";

function request(method, url, body) {
  const stream = Readable.from(body ? [Buffer.from(JSON.stringify(body))] : []);
  stream.method = method;
  stream.url = url;
  return stream;
}

function response() {
  return {
    headers: {},
    statusCode: 0,
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(value = "") {
      this.body = value ? JSON.parse(value) : {};
    },
  };
}

test("persists experiments and published variants", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-experiments-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", {
    name: "Pink vs red text",
    hypothesis: "Pink text holds attention longer",
    primaryMetric: "igReelsAvgWatchTime",
  }), createResponse, "");

  assert.equal(createResponse.statusCode, 201);
  assert.equal(createResponse.body.experiment.name, "Pink vs red text");
  const experimentId = createResponse.body.experiment.id;

  const variantResponse = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, {
    label: "Pink text hook",
    originalFilename: "IMG_1024.mp4",
    zernioPostId: "post_123",
    platformPostUrl: "https://instagram.com/reel/example",
    thumbnail: "data:image/jpeg;base64,dGVzdA==",
    status: "published",
  }), variantResponse, "");

  assert.equal(variantResponse.statusCode, 201);
  assert.equal(variantResponse.body.variant.label, "Pink text hook");

  const listResponse = response();
  await api.handle(request("GET", "/api/experiments"), listResponse, "");
  assert.equal(listResponse.body.experiments[0].variants.length, 1);
  assert.equal(listResponse.body.experiments[0].variants[0].zernioPostId, "post_123");
  assert.equal(listResponse.body.experiments[0].variants[0].thumbnail, "data:image/jpeg;base64,dGVzdA==");
});

test("refreshes and stores analytics for every variant", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-analytics-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });
  const originalFetch = global.fetch;
  context.after(() => {
    global.fetch = originalFetch;
  });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Hook test" }), createResponse, "");
  const experimentId = createResponse.body.experiment.id;
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, {
    label: "Question hook",
    zernioPostId: "post_analytics",
  }), response(), "");

  global.fetch = async () => new Response(JSON.stringify({
    status: "published",
    publishedAt: "2026-07-22T12:00:00.000Z",
    analytics: { views: 1200, reach: 980, saves: 44 },
    platformAnalytics: [{
      platform: "instagram",
      platformPostId: "ig_123",
      platformPostUrl: "https://instagram.com/reel/ig_123",
      syncStatus: "synced",
      analytics: { views: 1200, reach: 980, saves: 44, igReelsAvgWatchTime: 6200 },
    }],
  }), { status: 200, headers: { "Content-Type": "application/json" } });

  const refreshResponse = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/refresh`), refreshResponse, "sk_test");

  assert.equal(refreshResponse.statusCode, 200);
  const variant = refreshResponse.body.experiment.variants[0];
  assert.equal(variant.platformPostId, "ig_123");
  assert.equal(variant.analytics.views, 1200);
  assert.equal(variant.analytics.igReelsAvgWatchTime, 6200);
  assert.equal(variant.analyticsSnapshots.length, 1);
});

test("renames a published version", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-rename-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "List test" }), createResponse, "");
  const experimentId = createResponse.body.experiment.id;
  const variantResponse = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, { label: "List 2", zernioPostId: "post_rename" }), variantResponse, "");
  const variantId = variantResponse.body.variant.id;

  const renameResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}/variants/${variantId}`, { label: "  Big numbers list  " }), renameResponse, "");
  assert.equal(renameResponse.statusCode, 200);
  assert.equal(renameResponse.body.experiment.variants[0].label, "Big numbers list");

  const blankResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}/variants/${variantId}`, { label: "   " }), blankResponse, "");
  assert.equal(blankResponse.statusCode, 400);

  const missingResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}/variants/nope`, { label: "X" }), missingResponse, "");
  assert.equal(missingResponse.statusCode, 404);
});

test("picks and clears a winner", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-winner-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Hook test" }), createResponse, "");
  const experimentId = createResponse.body.experiment.id;
  const variantResponse = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, { label: "Numbers hook", zernioPostId: "post_winner" }), variantResponse, "");
  const variantId = variantResponse.body.variant.id;

  const pickResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { winnerId: variantId }), pickResponse, "");
  assert.equal(pickResponse.statusCode, 200);
  assert.equal(pickResponse.body.experiment.winnerId, variantId);
  assert.ok(pickResponse.body.experiment.decidedAt);

  const strangerResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { winnerId: "not-a-version" }), strangerResponse, "");
  assert.equal(strangerResponse.statusCode, 400);

  const clearResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { winnerId: null }), clearResponse, "");
  assert.equal(clearResponse.body.experiment.winnerId, null);
  assert.equal(clearResponse.body.experiment.decidedAt, null);
});

test("renames a test without touching its winner", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-test-name-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Oct 26 test" }), createResponse, "");
  const experimentId = createResponse.body.experiment.id;
  const variantResponse = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, { label: "A", zernioPostId: "post_name" }), variantResponse, "");
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { winnerId: variantResponse.body.variant.id }), response(), "");

  const renameResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { name: "  Hook test, round 3 " }), renameResponse, "");
  assert.equal(renameResponse.statusCode, 200);
  assert.equal(renameResponse.body.experiment.name, "Hook test, round 3");
  assert.equal(renameResponse.body.experiment.winnerId, variantResponse.body.variant.id);

  const blankResponse = response();
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { name: "  " }), blankResponse, "");
  assert.equal(blankResponse.statusCode, 400);
});

test("deletes a version and clears it as the winner", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-delete-version-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Hook test" }), createResponse, "");
  const experimentId = createResponse.body.experiment.id;
  const first = response();
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, { label: "A", zernioPostId: "post_a" }), first, "");
  await api.handle(request("POST", `/api/experiments/${experimentId}/variants`, { label: "B", zernioPostId: "post_b" }), response(), "");
  const firstId = first.body.variant.id;
  await api.handle(request("PATCH", `/api/experiments/${experimentId}`, { winnerId: firstId }), response(), "");

  const deleteResponse = response();
  await api.handle(request("DELETE", `/api/experiments/${experimentId}/variants/${firstId}`), deleteResponse, "");
  assert.equal(deleteResponse.statusCode, 200);
  assert.deepEqual(deleteResponse.body.experiment.variants.map((variant) => variant.label), ["B"]);
  assert.equal(deleteResponse.body.experiment.winnerId, null);

  const againResponse = response();
  await api.handle(request("DELETE", `/api/experiments/${experimentId}/variants/${firstId}`), againResponse, "");
  assert.equal(againResponse.statusCode, 404);
});

test("deletes a test", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-delete-test-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const api = createExperimentApi({ filePath: join(directory, "experiments.json") });

  const createResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Keep" }), createResponse, "");
  const goneResponse = response();
  await api.handle(request("POST", "/api/experiments", { name: "Delete me" }), goneResponse, "");

  const deleteResponse = response();
  await api.handle(request("DELETE", `/api/experiments/${goneResponse.body.experiment.id}`), deleteResponse, "");
  assert.equal(deleteResponse.statusCode, 200);

  const listResponse = response();
  await api.handle(request("GET", "/api/experiments"), listResponse, "");
  assert.deepEqual(listResponse.body.experiments.map((experiment) => experiment.name), ["Keep"]);

  const againResponse = response();
  await api.handle(request("DELETE", `/api/experiments/${goneResponse.body.experiment.id}`), againResponse, "");
  assert.equal(againResponse.statusCode, 404);
});

test("copies history from the old in-app file once, and leaves the old file alone", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-experiments-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const legacyFile = join(directory, "app", "experiments.json");
  const filePath = join(directory, "home", "experiments.json");
  await mkdir(join(directory, "app"));
  const old = { version: 1, experiments: [{ id: "exp_old", name: "Old test", createdAt: "2026-10-27T00:00:00.000Z", variants: [] }] };
  await writeFile(legacyFile, JSON.stringify(old));
  const api = createExperimentApi({ filePath, legacyFile });

  const listResponse = response();
  await api.handle(request("GET", "/api/experiments"), listResponse, "");
  assert.equal(listResponse.body.experiments[0].name, "Old test");
  assert.deepEqual(JSON.parse(await readFile(filePath, "utf8")), old);
  assert.deepEqual(JSON.parse(await readFile(legacyFile, "utf8")), old);
});

test("keeps a copy of yesterday's history before the first change of the day", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "trialr-experiments-"));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const filePath = join(directory, "experiments.json");
  const api = createExperimentApi({ filePath });

  await api.handle(request("POST", "/api/experiments", { name: "First" }), response(), "");
  assert.equal((await readdir(directory)).includes("backups"), false);

  await api.handle(request("POST", "/api/experiments", { name: "Second" }), response(), "");
  await api.handle(request("POST", "/api/experiments", { name: "Third" }), response(), "");
  const backups = await readdir(join(directory, "backups"));
  assert.equal(backups.length, 1);
  const saved = JSON.parse(await readFile(join(directory, "backups", backups[0]), "utf8"));
  assert.deepEqual(saved.experiments.map((e) => e.name), ["First"]);
});
