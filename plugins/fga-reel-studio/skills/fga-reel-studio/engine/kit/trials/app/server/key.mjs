import { chmod, readFile, rename, writeFile } from "node:fs/promises";
import { requestZernio } from "./zernio-api.mjs";

// The Zernio key the server uses right now: read from the environment or an .env when Trials starts,
// or pasted into the app, which saves it to the .env next to the history (app updates never replace that file).
let current = "";

export const getKey = () => current;

export function setKey(value) {
  current = String(value || "").trim();
}

function sendJson(response, status, payload) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(JSON.stringify(payload));
}

/** Sets ZERNIO_API_KEY in an .env file, keeping every other line. Written whole, then swapped in, readable only by its owner. */
export async function writeEnvKey(file, key) {
  let lines = [];
  try {
    lines = (await readFile(file, "utf8")).split("\n");
  } catch {
    // No file yet.
  }
  const line = `ZERNIO_API_KEY=${key}`;
  const at = lines.findIndex((entry) => /^\s*(export\s+)?ZERNIO_API_KEY\s*=/.test(entry));
  if (at >= 0) lines[at] = line;
  while (lines.length && !lines.at(-1).trim()) lines.pop();
  if (at < 0) lines.push(line);
  const tmp = `${file}.tmp`;
  await writeFile(tmp, `${lines.join("\n")}\n`, { mode: 0o600 });
  await rename(tmp, file);
  await chmod(file, 0o600);
}

/** POST /api/zernio/key {key}: checks the key with Zernio, then saves it and starts using it. Never sends it back. */
export async function handleKeyApi(request, response, envFile) {
  const url = new URL(request.url, "http://trials.local");
  if (url.pathname !== "/api/zernio/key" || request.method !== "POST") return false;

  // Only this page can set the key: other sites can't send JSON here without the browser blocking it first.
  const origin = request.headers.origin;
  const sameOrigin = !origin || new URL(origin).host === request.headers.host;
  if (!sameOrigin || !String(request.headers["content-type"] || "").includes("application/json")) {
    sendJson(response, 403, { error: "Set the key from the Trials page." });
    return true;
  }

  let key = "";
  try {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    key = String(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}").key || "").trim();
  } catch {
    // Handled as an empty key below.
  }
  if (!key || /\s/.test(key) || key.length > 500) {
    sendJson(response, 400, { error: "That doesn't look like a Zernio key. Copy it again from Zernio's API Keys page." });
    return true;
  }

  try {
    await requestZernio(key, "/profiles");
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      sendJson(response, 400, { error: "Zernio didn't accept that key. Copy it again from Zernio's API Keys page, and make sure it's a read-write key." });
    } else {
      sendJson(response, 502, { error: "Couldn't reach Zernio to check the key. Check your connection and try again." });
    }
    return true;
  }

  try {
    await writeEnvKey(envFile, key);
  } catch {
    sendJson(response, 500, { error: `The key works, but Trials couldn't save it to ${envFile}.` });
    return true;
  }
  setKey(key);
  sendJson(response, 200, { configured: true });
  return true;
}
