import { Capacitor } from "@capacitor/core";
import { describe, expect, it, vi } from "vitest";
import { isNative, platform } from "./platform";

describe("platform", () => {
  it("falls back to the browser outside the installed app", () => {
    expect(isNative()).toBe(false);
    expect(platform()).toBe("web");
  });

  it.each(["ios", "android"] as const)("reports %s inside the installed app", (name) => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    vi.spyOn(Capacitor, "getPlatform").mockReturnValue(name);

    expect(isNative()).toBe(true);
    expect(platform()).toBe(name);
  });
});
