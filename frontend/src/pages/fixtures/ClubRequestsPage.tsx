// Captain requests (design/src/ds/Screens.md, Admin 3, the Cancellations tab): Captains'
// requests to cancel or postpone their Team's match (FR-18), oldest first. A cancellation is
// accepted or declined here; a postponement needs a new time, so it opens the match, where
// the Admin picks it under Reschedule. What accepting does is the backend's decision.

import { useState } from "react";
import { Link } from "react-router";
import { api, type Schemas } from "../../api/client";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { formatMoment } from "../../format";
import { LoadState, send, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "../teams/shared";
import { NOT_AN_ADMIN } from "./ClubFixturesPage";
import { RequestStatus, requestDetail, requestTitle } from "./requests";
import { matchName } from "./shared";

type Request = Schemas["ClubCaptainRequest"];
type Filter = "pending" | "all";

export function ClubRequestsPage() {
  const { clubId, clubName } = useClub();
  const [filter, setFilter] = useState<Filter>("pending");
  const [requests, reload] = useLoad(
    () =>
      api.GET("/api/v1/clubs/{club_id}/captain-requests/", {
        params: { path: { club_id: clubId }, query: filter === "pending" ? { status: "pending" } : {} },
      }),
    `captain-requests-${clubId}-${filter}`,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function decide(request: Request, decision: "accept" | "decline") {
    setBusy(true);
    const path = { club_id: clubId, id: request.id };
    const failed = await send(() =>
      decision === "accept"
        ? api.POST("/api/v1/clubs/{club_id}/captain-requests/{id}/accept/", { params: { path }, body: {} })
        : api.POST("/api/v1/clubs/{club_id}/captain-requests/{id}/decline/", { params: { path }, body: {} }),
    );
    setBusy(false);
    setError(failed ? (failed.general ?? Object.values(failed.fields)[0] ?? "That didn't work.") : null);
    if (!failed) reload();
  }

  return (
    <main className="la-screen">
      <ScreenHeader
        title="Captain requests"
        back={{ label: "Fixtures", to: `/clubs/${clubId}/fixtures` }}
        caption={clubName}
      />
      <div className="la-choices">
        <ChoiceChip pressed={filter === "pending"} onToggle={() => setFilter("pending")}>
          Waiting
        </ChoiceChip>
        <ChoiceChip pressed={filter === "all"} onToggle={() => setFilter("all")}>
          All
        </ChoiceChip>
      </div>
      {error && <Banner status="cancelled" title={error} />}
      <LoadState result={requests} retry={reload} what="requests" forbidden={NOT_AN_ADMIN}>
        {(list) =>
          list.length === 0 ? (
            <p className="caption la-muted">No Captain is waiting for an answer.</p>
          ) : (
            <ul className="la-group" aria-label="Requests">
              {list.map((r) => (
                <li key={r.id} className="la-item">
                  <span className="la-item__body">
                    <span className="body-strong">{requestTitle(r)}</span>
                    <span className="caption">
                      {matchName(r.fixture)} · {formatMoment(r.fixture.kick_off)} · {r.fixture.pitch.name}
                    </span>
                    <span className="caption">{r.reason}</span>
                    <span className="caption la-muted">{requestDetail(r)}</span>
                    {r.status === "pending" && (
                      <span className="la-actions">
                        {r.kind === "cancel" ? (
                          <button
                            type="button"
                            className="la-btn la-btn--primary la-btn--sm"
                            disabled={busy}
                            onClick={() => void decide(r, "accept")}
                          >
                            Accept: {r.team.name} out
                          </button>
                        ) : (
                          <Link
                            className="la-btn la-btn--primary la-btn--sm"
                            to={`/clubs/${clubId}/fixtures/${r.fixture.id}`}
                          >
                            Pick the new time
                          </Link>
                        )}
                        <button
                          type="button"
                          className="la-btn la-btn--quiet la-btn--sm"
                          disabled={busy}
                          onClick={() => void decide(r, "decline")}
                        >
                          Decline
                        </button>
                      </span>
                    )}
                  </span>
                  <RequestStatus request={r} />
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
