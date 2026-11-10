import assert from "node:assert/strict";
import { mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import test from "node:test";
import { getKey, handleKeyApi, setKey, writeEnvKey } from "../server/key.mjs";

function request(body, headers = {}) {
  const stream = Readable.from([Buffer.from(JSON.stringify(body))]);
  stream.method = "POST";
  stream.url = "/api/zernio/key";
  stream.headers = { host: "127.0.0.1:5180", "content-type": "application/json", origin: "http://127.0.0.1:5180", ...headers };
  return stream;
}

function response() {
  return {
    statusCode: 0,
    setHeader() {},
    end(value = "") {
      this.body = value ? JSON.parse(value) : {};
    },
  };
}

function zernioAnswers(status) {
  const original = global.fetch;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, auth: options.headers.Authorization });
    return new Response(JSON.stringify(status === 200 ? { profiles: [] } : { error: "Invalid API key" }), { status });
  };
  return { calls, restore: () => (global.fetch = original) };
}

test("a key Zernio accepts is saved next to the history and used straight away, never sent back", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "trials-key-"));
  const env = join(dir, ".env");
  await writeFile(env, "# notes\nOTHER=1\nZERNIO_API_KEY=\n");
  setKey("");
  const zernio = zernioAnswers(200);
  t.after(zernio.restore);
  const res = response();
  assert.equal(await handleKeyApi(request({ key: "  sk_live_123  " }), res, env), true);
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.body, { configured: true });
  assert.equal(zernio.calls[0].auth, "Bearer sk_live_123");
  assert.equal(getKey(), "sk_live_123");
  assert.equal(await readFile(env, "utf8"), "# notes\nOTHER=1\nZERNIO_API_KEY=sk_live_123\n");
  assert.equal((await stat(env)).mode & 0o777, 0o600);
});

test("a key Zernio turns down is not saved", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "trials-key-"));
  const env = join(dir, ".env");
  setKey("sk_old");
  const zernio = zernioAnswers(401);
  t.after(zernio.restore);
  const res = response();
  await handleKeyApi(request({ key: "sk_wrong" }), res, env);
  assert.equal(res.statusCode, 400);
  assert.match(res.body.error, /didn't accept/);
  assert.equal(getKey(), "sk_old");
  await assert.rejects(readFile(env, "utf8"));
});

test("another website can't set the key, and nothing reaches Zernio", async (t) => {
  const zernio = zernioAnswers(200);
  t.after(zernio.restore);
  const res = response();
  await handleKeyApi(request({ key: "sk_attacker" }, { origin: "https://evil.example" }), res, "/nowhere/.env");
  assert.equal(res.statusCode, 403);
  const form = response();
  await handleKeyApi(request({ key: "sk_attacker" }, { "content-type": "text/plain", origin: undefined }), form, "/nowhere/.env");
  assert.equal(form.statusCode, 403);
  assert.equal(zernio.calls.length, 0);
});

test("writing the key adds the line when it's missing and keeps everything else", async () => {
  const dir = await mkdtemp(join(tmpdir(), "trials-key-"));
  const env = join(dir, ".env");
  await writeEnvKey(env, "sk_a");
  assert.equal(await readFile(env, "utf8"), "ZERNIO_API_KEY=sk_a\n");
  await writeFile(env, "PORT=1\n\n");
  await writeEnvKey(env, "sk_b");
  assert.equal(await readFile(env, "utf8"), "PORT=1\nZERNIO_API_KEY=sk_b\n");
});
