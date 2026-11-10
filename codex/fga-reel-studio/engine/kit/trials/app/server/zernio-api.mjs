const ZERNIO_BASE_URL = "https://zernio.com/api/v1";

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
    if (size > 1_000_000) {
      throw new Error("Request body is too large.");
    }
    chunks.push(chunk);
  }

  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export async function requestZernio(apiKey, path, options = {}) {
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    Accept: "application/json",
    ...options.headers,
  };

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${ZERNIO_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const raw = await response.text();
  let data;

  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { error: raw || `Zernio returned HTTP ${response.status}.` };
  }

  if (!response.ok) {
    const error = new Error(data.error || data.message || `Zernio returned HTTP ${response.status}.`);
    error.status = response.status;
    error.details = data.details;
    error.code = data.code;
    throw error;
  }

  return data;
}

function publicError(error) {
  return {
    error: error.message || "The Zernio request failed.",
    ...(error.code ? { code: error.code } : {}),
    ...(error.details ? { details: error.details } : {}),
  };
}

export async function handleZernioApi(request, response, apiKey) {
  const url = new URL(request.url, "http://trialr.local");

  if (!url.pathname.startsWith("/api/zernio/")) return false;

  if (url.pathname === "/api/zernio/status" && request.method === "GET") {
    sendJson(response, 200, { configured: Boolean(apiKey) });
    return true;
  }

  if (!apiKey) {
    sendJson(response, 503, {
      error: "Zernio is not connected yet. Paste your Zernio key on the Trials page.",
      code: "ZERNIO_NOT_CONFIGURED",
    });
    return true;
  }

  try {
    if (url.pathname === "/api/zernio/accounts" && request.method === "GET") {
      const data = await requestZernio(apiKey, "/accounts?platform=instagram&status=connected");
      sendJson(response, 200, data);
      return true;
    }

    if (url.pathname === "/api/zernio/profiles" && request.method === "GET") {
      const data = await requestZernio(apiKey, "/profiles");
      sendJson(response, 200, data);
      return true;
    }

    if (url.pathname === "/api/zernio/profiles/default" && request.method === "POST") {
      const data = await requestZernio(apiKey, "/profiles", {
        method: "POST",
        body: JSON.stringify({ name: "Trials", description: "Instagram Trial Reels" }),
      });
      sendJson(response, 201, data);
      return true;
    }

    if (url.pathname === "/api/zernio/connect" && request.method === "POST") {
      const body = await readJson(request);
      if (!body.profileId || !body.redirectUrl) {
        sendJson(response, 400, { error: "profileId and redirectUrl are required." });
        return true;
      }
      const query = new URLSearchParams({
        profileId: body.profileId,
        redirect_url: body.redirectUrl,
      });
      const data = await requestZernio(apiKey, `/connect/instagram?${query}`);
      sendJson(response, 200, data);
      return true;
    }

    if (url.pathname === "/api/zernio/presign" && request.method === "POST") {
      const body = await readJson(request);
      if (!body.filename || !body.contentType || !Number.isFinite(body.size)) {
        sendJson(response, 400, { error: "filename, contentType, and size are required." });
        return true;
      }
      const data = await requestZernio(apiKey, "/media/presign", {
        method: "POST",
        body: JSON.stringify({
          filename: body.filename,
          contentType: body.contentType,
          size: body.size,
        }),
      });
      sendJson(response, 200, data);
      return true;
    }

    if (url.pathname === "/api/zernio/posts" && request.method === "POST") {
      const body = await readJson(request);
      if (!body.accountId || !body.mediaUrl) {
        sendJson(response, 400, { error: "accountId and mediaUrl are required." });
        return true;
      }

      // A version with a time goes out later from Zernio's side, so the tab can close. Anything due within a minute posts now.
      const at = Date.parse(body.scheduledFor || "");
      const when = Number.isFinite(at) && at > Date.now() + 60_000
        ? { scheduledFor: new Date(at).toISOString(), timezone: "UTC" }
        : { publishNow: true };

      const data = await requestZernio(apiKey, "/posts", {
        method: "POST",
        headers: {
          "x-request-id": body.requestId || crypto.randomUUID(),
        },
        body: JSON.stringify({
          content: String(body.caption || "").slice(0, 2200),
          mediaItems: [{ type: "video", url: body.mediaUrl }],
          platforms: [
            {
              platform: "instagram",
              accountId: body.accountId,
              platformSpecificData: {
                trialParams: { graduationStrategy: "MANUAL" },
              },
            },
          ],
          ...when,
          ...(body.metadata && typeof body.metadata === "object" ? { metadata: body.metadata } : {}),
        }),
      });
      sendJson(response, 201, data);
      return true;
    }

    const postMatch = url.pathname.match(/^\/api\/zernio\/posts\/([^/]+)$/);
    if (postMatch && request.method === "GET") {
      const data = await requestZernio(apiKey, `/posts/${encodeURIComponent(postMatch[1])}`);
      sendJson(response, 200, data);
      return true;
    }

    sendJson(response, 404, { error: "Trials API route not found." });
    return true;
  } catch (error) {
    sendJson(response, error.status || 500, publicError(error));
    return true;
  }
}
