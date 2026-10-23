import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@capacitor/preferences", () => ({
  Preferences: { get: vi.fn(), set: vi.fn(), remove: vi.fn() },
}));

// The test setup already loaded storage.ts with the real plugin (through api/auth), so
// load fresh copies that see the mock.
async function load() {
  vi.resetModules();
  const { Capacitor } = await import("@capacitor/core");
  const { Preferences } = await import("@capacitor/preferences");
  const { storage } = await import("./storage");
  return { Capacitor, Preferences, storage };
}

let modules: Awaited<ReturnType<typeof load>>;
beforeEach(async () => {
  modules = await load();
});
afterEach(() => window.localStorage.clear());

describe("storage", () => {
  it("uses localStorage in the browser", async () => {
    const { Preferences, storage } = modules;

    await storage.set("k", "v");

    expect(window.localStorage.getItem("k")).toBe("v");
    expect(await storage.get("k")).toBe("v");
    await storage.remove("k");
    expect(await storage.get("k")).toBeNull();
    expect(Preferences.set).not.toHaveBeenCalled();
  });

  it("uses Capacitor Preferences inside the installed app", async () => {
    const { Capacitor, Preferences, storage } = modules;
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    vi.mocked(Preferences.get).mockResolvedValue({ value: "v" });

    await storage.set("k", "v");
    expect(await storage.get("k")).toBe("v");
    await storage.remove("k");

    expect(Preferences.set).toHaveBeenCalledWith({ key: "k", value: "v" });
    expect(Preferences.get).toHaveBeenCalledWith({ key: "k" });
    expect(Preferences.remove).toHaveBeenCalledWith({ key: "k" });
    expect(window.localStorage.getItem("k")).toBeNull();
  });
});
