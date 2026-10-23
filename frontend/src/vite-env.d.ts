/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Where the API lives. Unset in the browser (same origin); required in the installed app. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
