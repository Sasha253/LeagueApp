import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

const answer = (status: number, body: unknown) =>
  vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );

describe("HomePage", () => {
  it("says the API is connected when health is ok", async () => {
    vi.stubGlobal("fetch", answer(200, { status: "ok", database: "ok" }));
    render(<HomePage />);

    expect(await screen.findByText("API connected")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "League App" })).toBeInTheDocument();
  });

  it("says the database is down when health is 503", async () => {
    vi.stubGlobal("fetch", answer(503, { status: "error", database: "error" }));
    render(<HomePage />);

    expect(await screen.findByText("API can't reach the database")).toBeInTheDocument();
  });

  it("says the API is not reachable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    render(<HomePage />);

    expect(await screen.findByText("API not reachable")).toBeInTheDocument();
  });
});
