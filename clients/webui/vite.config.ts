import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function readArg(name: string): string | undefined {
  const argv = ((globalThis as { process?: { argv?: string[] } }).process?.argv) || [];
  const prefix = `--${name}=`;
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token.startsWith(prefix)) {
      return token.slice(prefix.length);
    }
    if (token === `--${name}`) {
      const next = argv[index + 1];
      if (next && !next.startsWith("--")) {
        return next;
      }
    }
  }
  return undefined;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const shellEnv = ((globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env) || {};
  const apiTarget =
    readArg("api-target") ||
    shellEnv.BANGSTATS_API_TARGET ||
    shellEnv.VITE_API_TARGET ||
    env.BANGSTATS_API_TARGET ||
    env.VITE_API_TARGET ||
    "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
