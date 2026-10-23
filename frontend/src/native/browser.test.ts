import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@capacitor/browser", () => ({
  Browser: { open: vi.fn(), addListener: vi.fn(), removeAllListeners: vi.fn() },
}));

async function load() {
  vi.resetModules();
  const { Capacitor } = await import("@capacitor/core");
  const { Browser } = await import("@capacitor/browser");
  const { openCheckout } = await import("./browser");
  return { Capacitor, Browser, openCheckout };
}

let modules: Awaited<ReturnType<typeof load>>;
beforeEach(async () => {
  modules = await load();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("openCheckout", () => {
  it("goes to the gateway in the same tab in a browser", async () => {
    const { Browser, openCheckout } = modules;
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });

    expect(await openCheckout("https://sandbox.payfast.co.za/eng/process?x=1")).toBe(false);

    expect(assign).toHaveBeenCalledWith("https://sandbox.payfast.co.za/eng/process?x=1");
    expect(Browser.open).not.toHaveBeenCalled();
  });

  it("opens the in-app browser in the installed app and settles when it is closed", async () => {
    const { Capacitor, Browser, openCheckout } = modules;
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    let finished: () => void = () => {};
    vi.mocked(Browser.addListener).mockImplementation(async (_event, listener) => {
      finished = listener;
      return { remove: vi.fn() };
    });
    vi.mocked(Browser.open).mockResolvedValue(undefined);

    let settled = false;
    const opening = openCheckout("https://sandbox.payfast.co.za/eng/process?x=1").then((back) => {
      settled = true;
      return back;
    });
    await vi.waitFor(() => expect(Browser.open).toHaveBeenCalled());
    expect(Browser.open).toHaveBeenCalledWith({
      url: "https://sandbox.payfast.co.za/eng/process?x=1",
      presentationStyle: "popover",
    });
    expect(settled).toBe(false);

    finished();
    expect(await opening).toBe(true);
    expect(settled).toBe(true);
    expect(Browser.removeAllListeners).toHaveBeenCalled();
  });

  it("fails when the in-app browser can't open", async () => {
    const { Capacitor, Browser, openCheckout } = modules;
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    vi.mocked(Browser.addListener).mockResolvedValue({ remove: vi.fn() });
    vi.mocked(Browser.open).mockRejectedValue(new Error("no browser"));

    await expect(openCheckout("https://example.com")).rejects.toThrow("no browser");
  });
});
