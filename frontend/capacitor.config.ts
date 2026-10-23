import type { CapacitorConfig } from "@capacitor/cli";

// One app for every club, so the id and name carry no club's name.
const config: CapacitorConfig = {
  appId: "za.co.leagueapp",
  appName: "League App",
  webDir: "dist",
  plugins: {
    // A push that arrives while the app is open still shows, and the inbox reloads.
    PushNotifications: { presentationOptions: ["badge", "sound", "alert"] },
  },
};

export default config;
