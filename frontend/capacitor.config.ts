import type { CapacitorConfig } from "@capacitor/cli";

// One app for every club, so the id and name carry no club's name.
const config: CapacitorConfig = {
  appId: "za.co.leagueapp",
  appName: "League App",
  webDir: "dist",
};

export default config;
