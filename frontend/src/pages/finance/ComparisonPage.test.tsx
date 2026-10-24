import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json } from "../../test/fakeApi";
import { openAs } from "../teams/testing";
import { ADMIN, AUTUMN, income, line, SPRING } from "./testing";

const SEASONS = "GET /api/v1/clubs/1/seasons/";
const COMPARISON = "GET /api/v1/clubs/1/finance/comparison/";

describe("ComparisonPage", () => {
  it("shows each Season's income lines and Nights, and narrows to picked Seasons", async () => {
    const queries: URLSearchParams[] = [];
    await openAs(
      "/clubs/1/finances/compare",
      {
        [SEASONS]: { status: 200, body: [SPRING, AUTUMN] },
        [COMPARISON]: (request: Request) => {
          const query = new URL(request.url).searchParams;
          queries.push(query);
          const both = [income(AUTUMN, { received: "12300.00", booking: line() }), income(SPRING)];
          return json(200, query.get("seasons") === "5" ? both.slice(1) : both);
        },
      },
      "Compare Seasons",
      ADMIN,
    );
    const user = userEvent.setup();

    const spring = await screen.findByRole("region", { name: "Spring 2026" });
    const autumn = screen.getByRole("region", { name: "Autumn 2026" });
    expect(queries[0]!.has("seasons")).toBe(false);
    expect(within(autumn).getByText("R 12,300")).toBeInTheDocument();
    expect(within(spring).getByText("R 19,650")).toBeInTheDocument();
    const lines = within(spring).getByRole("list", { name: "Spring 2026 income lines" });
    expect(within(lines).getByText("Card R 15,960 · Cash R 2,450")).toBeInTheDocument();
    expect(within(lines).getByText("R 540")).toBeInTheDocument();
    const nights = within(spring).getByRole("list", { name: "Spring 2026 by Night" });
    expect(within(nights).getByText("Tuesday")).toBeInTheDocument();
    expect(within(nights).getByText("League R 18,410 · Friendlies R 700")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Finances" })).toHaveAttribute("href", "/clubs/1/finances");

    await user.click(within(screen.getByRole("group", { name: "Seasons" })).getByRole("button", { name: "Spring 2026" }));
    await screen.findByRole("button", { name: "Spring 2026", pressed: true });
    await expect.poll(() => screen.queryByRole("region", { name: "Autumn 2026" })).toBeNull();
    expect(queries.at(-1)!.get("seasons")).toBe("5");
  });

  it("says when there are no Seasons", async () => {
    await openAs(
      "/clubs/1/finances/compare",
      { [SEASONS]: { status: 200, body: [] }, [COMPARISON]: { status: 200, body: [] } },
      "Compare Seasons",
      ADMIN,
    );
    expect(await screen.findByText("No Seasons yet. Add a Season in Club setup to compare its income.")).toBeInTheDocument();
  });

  it("tells a non-Admin the comparison is for Admins", async () => {
    await openAs(
      "/clubs/1/finances/compare",
      { [SEASONS]: { status: 403, body: {} }, [COMPARISON]: { status: 403, body: { detail: "No." } } },
      "Compare Seasons",
    );
    expect(await screen.findByText("Only this club's Admins can see its finances.")).toBeInTheDocument();
  });
});
