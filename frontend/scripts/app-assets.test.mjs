import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { artwork, launcherBackgroundXml, nightColours, targets } from "./app-assets.mjs";

const TOKENS = readFileSync(join(import.meta.dirname, "../src/styles/tokens.css"), "utf8");
const colours = { ground: "#0c1611", accent: "#cff25a" };

describe("app-assets", () => {
  it("reads the Night ground and accent from the design tokens", () => {
    expect(nightColours(TOKENS)).toEqual(colours);
  });

  it("refuses tokens without the Night colours", () => {
    expect(() => nightColours("[data-theme=\"day\"] { --ground: #ffffff; }")).toThrow(/Night/);
    expect(() => nightColours(':root, [data-theme="night"] { --ground: #0c1611; }')).toThrow(/--accent/);
  });

  it("draws the mark in accent on the ground, centred at the asked size", () => {
    const svg = artwork({ width: 200, height: 100, markHeight: 64, colours });

    expect(svg).toContain('width="200" height="100"');
    expect(svg).toContain('<rect width="200" height="100" fill="#0c1611"/>');
    expect(svg).toContain('stroke="#cff25a"');
    expect(svg).toContain("translate(100 50) scale(0.1)");
    expect(svg).not.toMatch(/<text/); // no club name, no lettering
  });

  it("draws round and transparent backgrounds", () => {
    expect(artwork({ width: 96, height: 96, markHeight: 50, colours, ground: "circle" })).toContain(
      '<circle cx="48" cy="48" r="48" fill="#0c1611"/>',
    );
    expect(artwork({ width: 96, height: 96, markHeight: 50, colours, ground: "none" })).not.toContain("#0c1611");
  });

  it("covers every icon and splash the iOS and Android projects use", () => {
    const list = targets();
    const byPath = Object.fromEntries(list.map((t) => [t.path, t]));

    const ios = byPath["ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"];
    expect(ios).toMatchObject({ width: 1024, height: 1024, opaque: true });
    expect(byPath["android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png"]).toMatchObject({ width: 192 });
    expect(byPath["android/app/src/main/res/mipmap-mdpi/ic_launcher_foreground.png"]).toMatchObject({
      width: 108,
      ground: "none",
    });
    expect(byPath["android/app/src/main/res/drawable-land-xxhdpi/splash.png"]).toMatchObject({ width: 1440, height: 960 });
    expect(byPath["assets/store/google-play-icon-512.png"]).toMatchObject({ width: 512, opaque: true });
    expect(list.filter((t) => t.path.includes("/Splash.imageset/"))).toHaveLength(3);
    expect(new Set(list.map((t) => t.path)).size).toBe(list.length);
  });

  it("keeps the adaptive icon's mark inside Android's safe circle", () => {
    for (const t of targets().filter((x) => x.path.endsWith("ic_launcher_foreground.png"))) {
      // The safe zone is the middle 66 of 108 dp; the mark is 3:4, so its diagonal must fit.
      const diagonal = Math.hypot(t.markHeight, (t.markHeight * 3) / 4);
      expect(diagonal).toBeLessThanOrEqual((t.width * 66) / 108);
    }
  });

  it("writes the adaptive icon background in the ground colour", () => {
    expect(launcherBackgroundXml(colours)).toContain('<color name="ic_launcher_background">#0C1611</color>');
  });
});
