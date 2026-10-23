import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@capacitor/barcode-scanner", () => ({
  CapacitorBarcodeScanner: { scanBarcode: vi.fn() },
  CapacitorBarcodeScannerTypeHint: { CODE_128: 3 },
}));

async function load() {
  vi.resetModules();
  const { Capacitor } = await import("@capacitor/core");
  const { CapacitorBarcodeScanner } = await import("@capacitor/barcode-scanner");
  const scanner = await import("./scanner");
  return { Capacitor, plugin: CapacitorBarcodeScanner, ...scanner };
}

let modules: Awaited<ReturnType<typeof load>>;
beforeEach(async () => {
  modules = await load();
});
afterEach(() => {
  vi.restoreAllMocks();
});

function native() {
  vi.spyOn(modules.Capacitor, "isNativePlatform").mockReturnValue(true);
}

describe("scanner", () => {
  it("can't scan in a browser and never opens the plugin there", async () => {
    const { canScan, scanBarcode, plugin } = modules;
    expect(canScan()).toBe(false);
    expect(await scanBarcode()).toEqual({ kind: "failed" });
    expect(plugin.scanBarcode).not.toHaveBeenCalled();
  });

  it("reads a Code 128 with the camera in the installed app", async () => {
    native();
    const { canScan, scanBarcode, plugin } = modules;
    vi.mocked(plugin.scanBarcode).mockResolvedValue({ ScanResult: " RK27104419 ", format: 3 } as never);

    expect(canScan()).toBe(true);
    expect(await scanBarcode()).toEqual({ kind: "code", code: "RK27104419" });
    expect(plugin.scanBarcode).toHaveBeenCalledWith(expect.objectContaining({ hint: 3 }));
  });

  it("answers cancelled when the camera is closed", async () => {
    native();
    const { scanBarcode, plugin } = modules;
    vi.mocked(plugin.scanBarcode).mockRejectedValue({ code: "OS-PLUG-BARC-0006", message: "cancelled" });
    expect(await scanBarcode()).toEqual({ kind: "cancelled" });
  });

  it("answers denied when camera access is refused", async () => {
    native();
    const { scanBarcode, plugin } = modules;
    vi.mocked(plugin.scanBarcode).mockRejectedValue({ code: "OS-PLUG-BARC-0007", message: "denied" });
    expect(await scanBarcode()).toEqual({ kind: "denied" });
  });

  it("answers failed on any other error", async () => {
    native();
    const { scanBarcode, plugin } = modules;
    vi.mocked(plugin.scanBarcode).mockRejectedValue(new Error("boom"));
    expect(await scanBarcode()).toEqual({ kind: "failed" });
  });
});
