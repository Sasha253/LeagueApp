import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { applyToPbxproj, checkRelease, MAX_BUILD, nextRelease, PBXPROJ, RELEASE_FILE } from "./app-version.mjs";

const PROJECT = `
  CURRENT_PROJECT_VERSION = 1;
  MARKETING_VERSION = 1.0;
  CURRENT_PROJECT_VERSION = 1;
  MARKETING_VERSION = 1.0;
`;

describe("app-version", () => {
  it("accepts a three-part version and a whole build number", () => {
    expect(checkRelease({ version: "1.2.3", build: 7 })).toEqual({ version: "1.2.3", build: 7 });
  });

  it.each([
    [{ version: "1.0", build: 1 }, /version must look like 1.0.0/],
    [{ version: "v1.0.0", build: 1 }, /version must look like/],
    [{ version: "1.0.0", build: 0 }, /build must be a whole number/],
    [{ version: "1.0.0", build: 1.5 }, /build must be a whole number/],
    [{ version: "1.0.0", build: "2" }, /build must be a whole number/],
    [{ version: "1.0.0", build: MAX_BUILD + 1 }, /build must be a whole number/],
  ])("refuses %j", (release, message) => {
    expect(() => checkRelease(release)).toThrow(message);
  });

  it("only ever moves the build up, with or without a new version", () => {
    expect(nextRelease({ version: "1.0.0", build: 4 })).toEqual({ version: "1.0.0", build: 5 });
    expect(nextRelease({ version: "1.0.0", build: 4 }, "1.1.0")).toEqual({ version: "1.1.0", build: 5 });
    expect(() => nextRelease({ version: "1.0.0", build: 4 }, "1.1")).toThrow(/version/);
  });

  it("writes the version and build into every iOS build configuration", () => {
    const out = applyToPbxproj(PROJECT, { version: "1.4.0", build: 12 });

    expect(out.match(/MARKETING_VERSION = 1\.4\.0;/g)).toHaveLength(2);
    expect(out.match(/CURRENT_PROJECT_VERSION = 12;/g)).toHaveLength(2);
    expect(out).not.toMatch(/= 1\.0;|= 1;/);
  });

  it("refuses an iOS project without the version settings", () => {
    expect(() => applyToPbxproj("nothing here", { version: "1.0.0", build: 1 })).toThrow(/MARKETING_VERSION/);
  });

  it("keeps release.json and the iOS project in step", () => {
    const release = checkRelease(JSON.parse(readFileSync(RELEASE_FILE, "utf8")));
    const project = readFileSync(PBXPROJ, "utf8");

    expect(applyToPbxproj(project, release)).toBe(project);
  });
});
