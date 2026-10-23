// This phone's push registration with the backend (POST /api/v1/devices/). The device id
// is kept so logout can remove it, and the phone gets no more pushes for that account.

import { api } from "../api/client";
import { platform } from "../native/platform";
import { unregisterPush } from "../native/push";
import { storage } from "../native/storage";

export const DEVICE_KEY = "leagueapp.device";

/** Registers (or moves to this account) the token the phone was given. */
export async function registerDevice(token: string): Promise<void> {
  const { data } = await api.POST("/api/v1/devices/", { body: { token, platform: platform() } });
  if (data) await storage.set(DEVICE_KEY, String(data.id));
}

/**
 * On logout, while the session still works: removes this phone's registration and stops
 * push. Best effort, so logging out works offline too.
 */
export async function forgetDevice(): Promise<void> {
  const saved = await storage.get(DEVICE_KEY);
  await storage.remove(DEVICE_KEY);
  await unregisterPush();
  const id = Number(saved);
  if (saved && Number.isInteger(id)) {
    await api.DELETE("/api/v1/devices/{device_id}/", { params: { path: { device_id: id } } }).catch(() => {});
  }
}
