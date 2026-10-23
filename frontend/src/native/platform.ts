// The one place the app asks which platform it runs on. In the browser (npm run dev)
// Capacitor reports "web", so every caller gets the browser fallback for free.

import { Capacitor } from "@capacitor/core";

export type Platform = "ios" | "android" | "web";

/** True inside the installed iOS or Android app, false in a browser. */
export function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/** The platform the app is running on. */
export function platform(): Platform {
  const name = Capacitor.getPlatform();
  return name === "ios" || name === "android" ? name : "web";
}
