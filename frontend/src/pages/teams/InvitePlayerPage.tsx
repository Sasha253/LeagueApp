// Invite a Player (docs/DECISIONS.md): the Admin invites an email to play in one of the
// club's active Teams. A Player in League App is in the Team at once; anyone else gets an
// email and joins when they sign up as a Player. Open invites are listed, to cancel.

import { useState } from "react";
import { useSearchParams } from "react-router";
import { api, type Schemas } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { formatMoment } from "../../format";
import { ConfirmButton, LoadState, NO_ERRORS, send, useClub, useLoad } from "../club/shared";
import { ScreenHeader } from "./shared";

type Invite = Schemas["TeamInvite"];

export function InvitePlayerPage() {
  const { clubId, clubName } = useClub();
  const path = { club_id: clubId };
  const [params] = useSearchParams();
  const [teams, reloadTeams] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/teams/", { params: { path, query: { status: "active" } } }),
    `club-teams-active-${clubId}`,
  );
  const [invites, reloadInvites] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/team-invites/", { params: { path } }),
    `team-invites-${clubId}`,
  );
  const [team, setTeam] = useState<number | null>(Number(params.get("team")) || null);
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [done, setDone] = useState<Invite | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function invite() {
    if (team === null) return;
    setBusy(true);
    setErrors(NO_ERRORS);
    setDone(null);
    try {
      const { data, error } = await api.POST("/api/v1/clubs/{club_id}/team-invites/", {
        params: { path },
        body: { team, email },
      });
      if (data) {
        setDone(data);
        setEmail("");
        reloadInvites();
        if (data.accepted) reloadTeams();
      } else {
        setErrors(formErrors(error));
      }
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  async function cancel(open: Invite) {
    const failed = await send(() =>
      api.DELETE("/api/v1/clubs/{club_id}/team-invites/{id}/", { params: { path: { ...path, id: open.id } } }),
    );
    setCancelError(failed?.general ?? null);
    if (!failed) reloadInvites();
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Invite a Player" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={clubName} />
      <LoadState result={teams} retry={reloadTeams} what="Teams">
        {(list) =>
          list.length === 0 ? (
            <Banner status="pending" title="No active Teams yet">
              Add a Team first, then invite its Players.
            </Banner>
          ) : (
            <form
              className="la-stack la-form"
              aria-label="Invite"
              onSubmit={(event) => {
                event.preventDefault();
                void invite();
              }}
            >
              <fieldset className="la-fieldset la-stack-2">
                <legend className="la-overline">Team</legend>
                <div className="la-choices">
                  {list.map((t) => (
                    <ChoiceChip
                      key={t.id}
                      pressed={team === t.id}
                      onToggle={() => setTeam(t.id)}
                      label={`${t.name}, ${t.division.name}, ${t.season.name}`}
                    >
                      {t.name}
                    </ChoiceChip>
                  ))}
                </div>
                {errors.fields.team && <span className="la-field__error">{errors.fields.team}</span>}
              </fieldset>
              <TextField
                label="Email"
                type="email"
                value={email}
                help="Someone who plays in League App is in the Team at once. Anyone else gets an email to sign up."
                onChange={(event) => setEmail(event.target.value)}
                error={errors.fields.email}
              />
              {errors.general && <Banner status="cancelled" title={errors.general} />}
              {done && (
                <Banner status="confirmed" title={done.accepted ? `In ${done.team_name}` : "Invite sent"}>
                  {done.accepted
                    ? `${done.email} is now a Player in ${done.team_name}.`
                    : `${done.email} joins ${done.team_name} when they sign up as a Player.`}
                </Banner>
              )}
              <button
                type="submit"
                className="la-btn la-btn--primary la-btn--block"
                disabled={busy || team === null || !email.trim()}
              >
                Invite
              </button>
            </form>
          )
        }
      </LoadState>
      <section className="la-stack-2" aria-labelledby="open-invites">
        <h2 id="open-invites" className="la-overline">
          Waiting to sign up
        </h2>
        <LoadState result={invites} retry={reloadInvites} what="invites">
          {(open) =>
            open.length === 0 ? (
              <p className="body la-muted">No open invites.</p>
            ) : (
              <ul className="la-group">
                {open.map((o) => (
                  <li key={o.id} className="la-item">
                    <div className="la-item__body">
                      <span className="body-strong">{o.email}</span>
                      <span className="caption la-muted">
                        {o.team_name} · invited {formatMoment(o.created_at)}
                      </span>
                    </div>
                    <ConfirmButton label="Cancel" confirmLabel={`Cancel invite for ${o.email}`} onConfirm={() => cancel(o)} />
                  </li>
                ))}
              </ul>
            )
          }
        </LoadState>
        {cancelError && <Banner status="cancelled" title={cancelError} />}
      </section>
    </main>
  );
}
