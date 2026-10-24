/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the API lives. Unset in the browser (same origin); required in the installed app. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** The app's store version ("1.0.0") and build number ("12"), from release.json. */
declare const __APP_VERSION__: string;
declare const __APP_BUILD__: string;
