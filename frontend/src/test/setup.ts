import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// No test talks to a real server: each test stubs fetch with the answer it needs.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
