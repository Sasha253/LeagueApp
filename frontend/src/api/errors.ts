// Turns a DRF error body into messages a screen can show next to its fields.

export type FormErrors = { fields: Record<string, string>; general: string | null };

const UNREACHABLE = "Can't reach League App. Check your connection and try again.";

/** DRF answers {field: ["message"]}, {non_field_errors: [...]} or {detail: "..."}. */
export function formErrors(body: unknown): FormErrors {
  const fields: Record<string, string> = {};
  let general: string | null = null;
  if (!body || typeof body !== "object") return { fields, general: UNREACHABLE };

  const collect = (value: unknown, prefix: string) => {
    if (typeof value === "string") {
      if (prefix === "detail" || prefix === "non_field_errors") general ??= value;
      else fields[prefix] ??= value;
    } else if (Array.isArray(value)) {
      if (value.length) collect(value[0], prefix);
    } else if (value && typeof value === "object") {
      for (const [key, inner] of Object.entries(value)) {
        collect(inner, key === "non_field_errors" || key === "detail" ? key : prefix ? `${prefix}.${key}` : key);
      }
    }
  };
  collect(body, "");
  return { fields, general };
}

export const unreachable: FormErrors = { fields: {}, general: UNREACHABLE };
