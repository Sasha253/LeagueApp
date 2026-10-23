// Opening the payment gateway's hosted page (PayFast). Card details are typed there, never
// in the app (CLAUDE.md). Inside the installed app the page opens in the in-app browser
// (@capacitor/browser) and the promise settles when the Player closes it, so the screen can
// check the payment. In the browser (npm run dev) the tab goes to the gateway, which sends
// the Player back to the app's return page (PAYMENT_RETURN_URL) afterwards.

import { Browser } from "@capacitor/browser";
import { isNative } from "./platform";

/** Opens the gateway at `url`. True once the Player is back in the app (the in-app browser
 * was closed); false when this page is leaving for the gateway (browser). */
export async function openCheckout(url: string): Promise<boolean> {
  if (!isNative()) {
    window.location.assign(url);
    return false;
  }
  await new Promise<void>((resolve, reject) => {
    void Browser.addListener("browserFinished", () => {
      void Browser.removeAllListeners();
      resolve();
    })
      .then(() => Browser.open({ url, presentationStyle: "popover" }))
      .catch((error: unknown) => {
        void Browser.removeAllListeners();
        reject(error instanceof Error ? error : new Error(String(error)));
      });
  });
  return true;
}
