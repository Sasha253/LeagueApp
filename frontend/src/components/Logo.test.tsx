import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Logo } from "./Logo";

describe("Logo", () => {
  it("reads as League App, with the mark hidden from screen readers", () => {
    const { container } = render(<Logo />);

    expect(screen.getByText("League App")).toBeInTheDocument();
    const mark = container.querySelector("svg")!;
    expect(mark).toHaveAttribute("aria-hidden", "true");
  });

  it("paints the bars from tokens, not fixed colours", () => {
    const { container } = render(<Logo />);

    const fills = [...container.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"));
    expect(fills).toEqual(["var(--accent-ink)", "var(--ink)"]);
  });
});
