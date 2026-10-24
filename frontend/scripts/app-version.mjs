// The app's version and build number, kept in frontend/release.json (one place for both
// stores). Android's Gradle build reads release.json itself (versionName, versionCode);
// this script writes it into the iOS project (MARKETING_VERSION, CURRENT_PROJECT_VERSION).
//
//   npm run version:apply            write release.json into the iOS project
//   npm run version:bump             build + 1, then apply (every store upload needs a new build)
//   npm run version:set -- 1.1.0     a new version, build + 1, then apply
//
// The stores refuse an upload whose build number was used before, so the build only goes up.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const RELEASE_FILE = join(ROOT, "release.json");
export const PBXPROJ = join(ROOT, "ios/App/App.xcodeproj/project.pbxproj");

/** Highest versionCode Google Play accepts. */
export const MAX_BUILD = 2100000000;

/** Checks a release.json value; answers it, or throws saying what is wrong. */
export function checkRelease(release) {
  const { version, build } = release ?? {};
  if (typeof version !== "string" || !/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`version must look like 1.0.0, not ${JSON.stringify(version)}`);
  }
  if (!Number.isInteger(build) || build < 1 || build > MAX_BUILD) {
    throw new Error(`build must be a whole number from 1 to ${MAX_BUILD}, not ${JSON.stringify(build)}`);
  }
  return { version, build };
}

/** The release with its build number one higher, and a new version if one is given. */
export function nextRelease(release, version) {
  const current = checkRelease(release);
  return checkRelease({ version: version ?? current.version, build: current.build + 1 });
}

/** The iOS project text with every MARKETING_VERSION and CURRENT_PROJECT_VERSION set. */
export function applyToPbxproj(text, release) {
  const { version, build } = checkRelease(release);
  const settings = [
    [/MARKETING_VERSION = [^;]*;/g, `MARKETING_VERSION = ${version};`],
    [/CURRENT_PROJECT_VERSION = [^;]*;/g, `CURRENT_PROJECT_VERSION = ${build};`],
  ];
  return settings.reduce((out, [pattern, value]) => {
    if (out.search(pattern) === -1) throw new Error(`The iOS project has no ${value.split(" ")[0]}`);
    return out.replace(pattern, value);
  }, text);
}

function readRelease() {
  return checkRelease(JSON.parse(readFileSync(RELEASE_FILE, "utf8")));
}

function apply(release) {
  writeFileSync(PBXPROJ, applyToPbxproj(readFileSync(PBXPROJ, "utf8"), release));
  console.log(`League App ${release.version} (${release.build}): release.json and the iOS project agree.`);
}

function main([command, version]) {
  if (command === "apply") return apply(readRelease());
  if (command === "bump" || command === "set") {
    if (command === "set" && !version) throw new Error("Give the new version: npm run version:set -- 1.1.0");
    const release = nextRelease(readRelease(), command === "set" ? version : undefined);
    writeFileSync(RELEASE_FILE, `${JSON.stringify(release, null, 2)}\n`);
    return apply(release);
  }
  throw new Error("Use apply, bump or set <version>");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
