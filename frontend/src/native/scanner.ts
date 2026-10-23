// Scanning a Payment Barcode at the gate with the device camera (FR-23). Inside the
// installed app this opens the official Capacitor barcode plugin (@capacitor/barcode-scanner):
// its own full-screen camera view with a torch button, looking for Code 128, the format the
// PaymentTicket draws. In a browser (npm run dev) there is no camera scanning: the screen
// offers typing the code instead (canScan() is false). The plugin is loaded only when it is
// used, so the browser bundle doesn't carry it.

import { isNative } from "./platform";

export type ScanOutcome =
  /** The camera read a barcode: its text, as the backend expects it. */
  | { kind: "code"; code: string }
  /** The user closed the camera without scanning. */
  | { kind: "cancelled" }
  /** Camera access was refused: type the code instead. */
  | { kind: "denied" }
  /** Anything else went wrong: type the code instead. */
  | { kind: "failed" };

// The plugin's error codes (OS-PLUG-BARC-xxxx), the same on iOS and Android.
const CANCELLED = "OS-PLUG-BARC-0006";
const DENIED = "OS-PLUG-BARC-0007";

/** True when the device camera can scan (the installed app). */
export function canScan(): boolean {
  return isNative();
}

function errorCode(error: unknown): string {
  if (error && typeof error === "object" && "code" in error) return String(error.code);
  return "";
}

/** Opens the camera and waits for a Payment Barcode. Never throws. */
export async function scanBarcode(): Promise<ScanOutcome> {
  if (!canScan()) return { kind: "failed" };
  try {
    const { CapacitorBarcodeScanner, CapacitorBarcodeScannerTypeHint } = await import(
      "@capacitor/barcode-scanner"
    );
    const { ScanResult } = await CapacitorBarcodeScanner.scanBarcode({
      hint: CapacitorBarcodeScannerTypeHint.CODE_128,
      scanInstructions: "Hold the barcode inside the frame.",
      cancelButtonAccessibilityLabel: "Close the camera",
      torchButtonOnAccessibilityLabel: "Turn the torch off",
      torchButtonOffAccessibilityLabel: "Turn the torch on",
    });
    const code = ScanResult.trim();
    return code ? { kind: "code", code } : { kind: "cancelled" };
  } catch (error) {
    const code = errorCode(error);
    if (code === CANCELLED) return { kind: "cancelled" };
    if (code === DENIED) return { kind: "denied" };
    return { kind: "failed" };
  }
}
