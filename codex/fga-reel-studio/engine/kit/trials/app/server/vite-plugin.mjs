import { join } from "node:path";
import { loadEnv } from "vite";
import { DATA_DIR, handleExperimentApi } from "./experiment-api.mjs";
import { getKey, handleKeyApi, setKey } from "./key.mjs";
import { handleZernioApi } from "./zernio-api.mjs";

export function trialrApiPlugin() {
  setKey(process.env.ZERNIO_API_KEY);

  return {
    name: "trialr-zernio-api",
    configResolved(config) {
      // The app's own .env first, then the one next to the history, which app updates never replace.
      const env = loadEnv(config.mode, config.root, "");
      const kept = loadEnv(config.mode, DATA_DIR, "");
      setKey(process.env.ZERNIO_API_KEY || env.ZERNIO_API_KEY || kept.ZERNIO_API_KEY);
    },
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        if (await handleKeyApi(request, response, join(DATA_DIR, ".env"))) return;
        if (await handleExperimentApi(request, response, getKey())) return;
        const handled = await handleZernioApi(request, response, getKey());
        if (!handled) next();
      });
    },
  };
}
