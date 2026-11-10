import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { DATA_DIR, handleExperimentApi } from "./experiment-api.mjs";
import { getKey, handleKeyApi, setKey } from "./key.mjs";
import { handleZernioApi } from "./zernio-api.mjs";

// The app's own .env first, then the one next to the history. Neither overrides the environment.
for (const file of [fileURLToPath(new URL("../.env", import.meta.url)), join(DATA_DIR, ".env")]) {
  try {
    process.loadEnvFile?.(file);
  } catch {
    // No .env there.
  }
}

const root = fileURLToPath(new URL("../dist/client", import.meta.url));
const port = Number(process.env.PORT || 4173);
setKey(process.env.ZERNIO_API_KEY);
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};

function serveFile(response, path) {
  response.statusCode = 200;
  response.setHeader("Content-Type", contentTypes[extname(path)] || "application/octet-stream");
  createReadStream(path).pipe(response);
}

createServer(async (request, response) => {
  if (await handleKeyApi(request, response, join(DATA_DIR, ".env"))) return;
  if (await handleExperimentApi(request, response, getKey())) return;
  if (await handleZernioApi(request, response, getKey())) return;

  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  const requested = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.(\/|\\|$))+/, "");
  const filePath = join(root, requested === "/" ? "index.html" : requested);

  if (filePath.startsWith(root) && existsSync(filePath) && statSync(filePath).isFile()) {
    serveFile(response, filePath);
    return;
  }

  const indexPath = join(root, "index.html");
  if (existsSync(indexPath)) {
    serveFile(response, indexPath);
    return;
  }

  response.statusCode = 503;
  response.end("Build Trials first with npm run build.");
}).listen(port, process.env.HOST || "127.0.0.1", () => {
  console.log(`Trials is running on http://localhost:${port}`);
});
