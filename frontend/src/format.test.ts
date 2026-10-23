import { describe, expect, it } from "vitest";
import { formatDate, formatMoment, formatRand, formatTime, localDate } from "./format";

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

describe("localDate", () => {
  it("gives the date in South Africa, not in UTC", () => {
    expect(localDate("2026-10-26T23:30:00Z")).toBe("2026-10-27");
    expect(localDate("2026-10-26T21:00:00Z")).toBe("2026-10-26");
  });
});

describe("formatTime", () => {
  it("gives the 24-hour time in South Africa", () => {
    expect(formatTime("2026-10-27T17:40:00Z")).toBe("19:40");
    expect(formatTime("2026-10-27T19:40:00+02:00")).toBe("19:40");
    expect(formatTime("2026-10-26T22:05:00Z")).toBe("00:05");
  });
});

describe("formatMoment", () => {
  it("gives the South African date and time", () => {
    expect(formatMoment("2026-10-26T22:05:00Z")).toBe("Tue 27 Oct · 00:05");
  });
});
