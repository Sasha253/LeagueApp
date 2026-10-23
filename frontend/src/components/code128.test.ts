import { describe, expect, it } from "vitest";
import { CODE128_PATTERNS, code128Bars, code128Values, QUIET_ZONE } from "./code128";

describe("Code 128", () => {
  it("has 107 distinct symbols of 11 modules each (Stop is 13)", () => {
    expect(CODE128_PATTERNS).toHaveLength(107);
    expect(new Set(CODE128_PATTERNS).size).toBe(107);
    CODE128_PATTERNS.forEach((pattern, value) => {
      const modules = [...pattern].reduce((sum, digit) => sum + Number(digit), 0);
      expect(modules).toBe(value === 106 ? 13 : 11);
    });
  });

  it("starts with Start B, ends with Stop, and carries the check symbol", () => {
    // Check: (104 + 48×1 + 42×2 + 42×3 + 17×4 + 18×5 + 19×6 + 35×7) mod 103 = 879 mod 103 = 55.
    expect(code128Values("PJJ123C")).toEqual([104, 48, 42, 42, 17, 18, 19, 35, 55, 106]);
  });

  it("draws Start B as 11010010000", () => {
    const { bars } = code128Bars("");
    const first = bars.slice(0, 3).map((bar) => [bar.x - QUIET_ZONE, bar.width]);
    expect(first).toEqual([
      [0, 2],
      [3, 1],
      [6, 1],
    ]);
  });

  it("is as wide as its symbols and both quiet zones", () => {
    // Start, 10 characters and the check: 12 × 11 modules, Stop 13.
    expect(code128Bars("RK27104419").width).toBe(12 * 11 + 13 + 2 * QUIET_ZONE);
  });

  it("refuses what set B can't encode", () => {
    expect(() => code128Values("é")).toThrow();
  });
});
