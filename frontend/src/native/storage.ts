// Small key-value storage that survives app restarts. Inside the installed app it uses
// Capacitor Preferences; in the browser (npm run dev) it falls back to localStorage.

import { Preferences } from "@capacitor/preferences";
import { isNative } from "./platform";

export const storage = {
  async get(key: string): Promise<string | null> {
    if (isNative()) return (await Preferences.get({ key })).value;
    return window.localStorage.getItem(key);
  },

  async set(key: string, value: string): Promise<void> {
    if (isNative()) await Preferences.set({ key, value });
    else window.localStorage.setItem(key, value);
  },

  async remove(key: string): Promise<void> {
    if (isNative()) await Preferences.remove({ key });
    else window.localStorage.removeItem(key);
  },
};
