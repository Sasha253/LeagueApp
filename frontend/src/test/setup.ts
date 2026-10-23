import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { setTokens } from "../api/auth";

// No test talks to a real server: each test stubs fetch with the answer it needs.
afterEach(async () => {
  cleanup();
  vi.unstubAllGlobals();
  await setTokens(null);
  window.localStorage.clear();
});
