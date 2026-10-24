import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";

// The store version and build (release.json, npm run version:bump), shown on Profile.
const release = JSON.parse(readFileSync(new URL("./release.json", import.meta.url), "utf8")) as {
  version: string;
  build: number;
};

// Django's dev server (make run). 127.0.0.1 rather than localhost: on Windows
// localhost tries IPv6 first and stalls before falling back.
const DJANGO_DEV_SERVER = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(release.version),
    __APP_BUILD__: JSON.stringify(String(release.build)),
  },
  server: {
    port: 5173,
    strictPort: true,
    // Same-origin in the browser, so session and CSRF cookies just work.
    proxy: {
      "/api": { target: DJANGO_DEV_SERVER },
      "/admin": { target: DJANGO_DEV_SERVER },
      "/static": { target: DJANGO_DEV_SERVER },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
