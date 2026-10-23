import { describe, expect, it } from "vitest";
import { formatDate, formatRand } from "./format";

describe("formatRand", () => {
  it.each([
    ["350.00", "R 350"],
    ["18550.00", "R 18,550"],
    ["70.50", "R 70.50"],
    ["1234567.05", "R 1,234,567.05"],
    ["0.00", "R 0"],
    ["-490.00", "-R 490"],
  ])("%s → %s", (amount, shown) => expect(formatRand(amount)).toBe(shown));
});

describe("formatDate", () => {
  it("shows the weekday, day and month", () => {
    expect(formatDate("2026-10-27")).toBe("Tue 27 Oct");
    expect(formatDate("2026-08-04")).toBe("Tue 4 Aug");
  });
});
