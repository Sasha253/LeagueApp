// Thin typed client over the backend API. Types come from schema.d.ts, which
// `npm run gen:api` regenerates from the OpenAPI schema; never edit them by hand.

import createClient from "openapi-fetch";
import { authMiddleware } from "./auth";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Health = Schemas["Health"];
export type Me = Schemas["Me"];
export type Night = Schemas["Night"];
export type Position = Schemas["PositionEnum"];

// The installed app runs on its own origin, so its build sets VITE_API_BASE_URL. The
// browser uses its own origin: the Vite dev server proxies /api to Django, and
// production serves both.
export const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;

export const api = createClient<paths>({
  baseUrl,
  // Read the global fetch on every call, not once at import, so tests can stub it.
  fetch: (request) => globalThis.fetch(request),
});

api.use(authMiddleware);
