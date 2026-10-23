// Saving a file the API sends, such as an import template. The browser downloads it.
// The installed app can't save files yet (that needs the Filesystem and Share plugins),
// so it answers false and the screen says to download from a browser.

import { isNative } from "./platform";

/** Saves `blob` as `name`. False when this platform can't save files. */
export function saveFile(blob: Blob, name: string): boolean {
  if (isNative()) return false;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  // Let the click start the download before the URL goes.
  setTimeout(() => URL.revokeObjectURL(url), 0);
  return true;
}
