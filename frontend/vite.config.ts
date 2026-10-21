import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Django's dev server (make run). 127.0.0.1 rather than localhost: on Windows
// localhost tries IPv6 first and stalls before falling back.
const DJANGO_DEV_SERVER = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
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
