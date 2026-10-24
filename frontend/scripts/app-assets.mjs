// App icons and splash screens for the App Store and Google Play: `npm run assets`.
//
// The design system has no logo yet (design/src/ds/README.md, Iconography), so the icon is
// a plain mark drawn from its tokens: a pitch outline in `accent` on the Night `ground`,
// the look of floodlit night football. No club's crest, no text. Colours are read from
// src/styles/tokens.css, so a token change and a re-run update every image. Replace
// `pitchMark` when a brand mark exists; every size below follows from it.
//
// Writes: the iOS AppIcon (1024, no transparency) and launch image, the Android launcher
// icons (legacy, round, adaptive foreground) and splash images, and the store icons in
// assets/store/ (App Store 1024, Google Play 512).

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const RES = "android/app/src/main/res";
const IOS_ASSETS = "ios/App/App/Assets.xcassets";

/** The mark is drawn on a 1024 square; this is its own height in that square. */
const MARK_HEIGHT = 640;

/** The Night theme colours from tokens.css (the app's default theme). */
export function nightColours(css) {
  const block = css.match(/:root,\s*\[data-theme="night"\]\s*\{([^}]*)\}/)?.[1];
  if (!block) throw new Error("tokens.css has no Night theme block");
  const token = (name) => {
    const value = block.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`))?.[1];
    if (!value) throw new Error(`tokens.css has no --${name} colour`);
    return value.toLowerCase();
  };
  return { ground: token("ground"), accent: token("accent") };
}

/** A pitch seen from above: outline, halfway line, centre circle and both goal areas. */
export function pitchMark(accent) {
  return [
    `<g fill="none" stroke="${accent}" stroke-width="44" stroke-linejoin="round">`,
    `<rect x="272" y="192" width="480" height="640" rx="40"/>`,
    `<line x1="272" y1="512" x2="752" y2="512"/>`,
    `<circle cx="512" cy="512" r="96"/>`,
    `<path d="M416 192 V280 H608 V192"/>`,
    `<path d="M416 832 V744 H608 V832"/>`,
    `</g>`,
  ].join("");
}

/**
 * An SVG of `width` × `height` with the mark centred, `markHeight` pixels tall.
 * `ground` paints the background: "square", "circle" or "none" (transparent).
 */
export function artwork({ width, height, markHeight, colours, ground = "square" }) {
  const scale = markHeight / MARK_HEIGHT;
  const background =
    ground === "square"
      ? `<rect width="${width}" height="${height}" fill="${colours.ground}"/>`
      : ground === "circle"
        ? `<circle cx="${width / 2}" cy="${height / 2}" r="${Math.min(width, height) / 2}" fill="${colours.ground}"/>`
        : "";
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    background +
    `<g transform="translate(${width / 2} ${height / 2}) scale(${scale}) translate(-512 -512)">` +
    pitchMark(colours.accent) +
    `</g></svg>`
  );
}

const DENSITIES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
// Android splash images (dp at mdpi, portrait); landscape swaps them.
const SPLASH_DP = { width: 320, height: 480 };

/** Every image to write: path (from frontend/), size, and how it is drawn. */
export function targets() {
  const list = [];
  const icon = (path, size, markShare, ground, opaque = false) =>
    list.push({ path, width: size, height: size, markHeight: Math.round(size * markShare), ground, opaque });
  const splash = (path, width, height) =>
    list.push({ path, width, height, markHeight: Math.round(Math.min(width, height) * 0.3), ground: "square", opaque: true });

  // iOS: one 1024 icon (no transparency allowed) and the launch image (LaunchScreen.storyboard
  // fills the screen with it, so the mark sits small in the middle of a large square).
  icon(`${IOS_ASSETS}/AppIcon.appiconset/AppIcon-512@2x.png`, 1024, 0.62, "square", true);
  for (const name of ["splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"]) {
    list.push({ path: `${IOS_ASSETS}/Splash.imageset/${name}`, width: 2732, height: 2732, markHeight: 406, ground: "square", opaque: true });
  }

  // Android launcher icons. The adaptive foreground keeps the mark inside the 66 dp safe
  // circle of its 108 dp layer; the background is the ground colour (values/).
  for (const [density, factor] of Object.entries(DENSITIES)) {
    icon(`${RES}/mipmap-${density}/ic_launcher.png`, 48 * factor, 0.62, "square", true);
    icon(`${RES}/mipmap-${density}/ic_launcher_round.png`, 48 * factor, 0.56, "circle");
    icon(`${RES}/mipmap-${density}/ic_launcher_foreground.png`, 108 * factor, 0.4, "none");
    const w = SPLASH_DP.width * factor;
    const h = SPLASH_DP.height * factor;
    splash(`${RES}/drawable-port-${density}/splash.png`, w, h);
    splash(`${RES}/drawable-land-${density}/splash.png`, h, w);
  }
  splash(`${RES}/drawable/splash.png`, 480, 320);

  // Store listing icons: the App Store's comes from the app itself; Google Play asks for 512.
  icon("assets/store/app-store-icon-1024.png", 1024, 0.62, "square", true);
  icon("assets/store/google-play-icon-512.png", 512, 0.62, "square", true);
  return list;
}

/** The Android colour resource for the adaptive icon background. */
export function launcherBackgroundXml(colours) {
  return `<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">${colours.ground.toUpperCase()}</color>\n</resources>\n`;
}

async function main() {
  const { default: sharp } = await import("sharp");
  const colours = nightColours(readFileSync(join(ROOT, "src/styles/tokens.css"), "utf8"));
  for (const target of targets()) {
    const file = join(ROOT, target.path);
    mkdirSync(dirname(file), { recursive: true });
    let image = sharp(Buffer.from(artwork({ ...target, colours })));
    if (target.opaque) image = image.flatten({ background: colours.ground }).removeAlpha();
    await image.png().toFile(file);
  }
  writeFileSync(join(ROOT, `${RES}/values/ic_launcher_background.xml`), launcherBackgroundXml(colours));
  writeFileSync(join(ROOT, "assets/icon.svg"), `${artwork({ width: 1024, height: 1024, markHeight: 635, colours })}\n`);
  console.log(`Wrote ${targets().length} images from the Night tokens (${colours.ground}, ${colours.accent}).`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
