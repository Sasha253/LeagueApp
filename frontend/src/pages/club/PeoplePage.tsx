// People: the Club's Admins and Referees. An Admin invites by email; an account with that
// email gets the role at once, and anyone else gets it when they sign up with it.

import { useState } from "react";
import { api, type Schemas } from "../../api/client";
import type { FormErrors } from "../../api/errors";
import { useAuth } from "../../auth/AuthProvider";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { ConfirmButton, LoadState, NO_ERRORS, send, SetupHeader, useClub, useLoad } from "./shared";

type Role = Schemas["RoleEnum"];
const ROLE_LABELS: Record<Role, string> = { admin: "Admin", referee: "Referee" };

export function PeoplePage() {
  const { clubId } = useClub();
  const { state } = useAuth();
  const myId = state.status === "signedIn" ? state.me.id : null;
  const path = { club_id: clubId };
  const [data, reload] = useLoad(async () => {
    const [members, invites] = await Promise.all([
      api.GET("/api/v1/clubs/{club_id}/members/", { params: { path } }),
      api.GET("/api/v1/clubs/{club_id}/invites/", { params: { path } }),
    ]);
    const failed = !members.data ? members : !invites.data ? invites : null;
    if (failed) return { error: failed.error, response: failed.response };
    return { data: { members: members.data!, invites: invites.data! }, response: members.response };
  }, `people-${clubId}`);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function act(call: () => Promise<{ error?: unknown; response: Response }>) {
    setNotice(null);
    const failed = await send(call);
    setError(failed?.general ?? null);
    if (!failed) reload();
  }

  return (
    <main className="la-screen">
      <SetupHeader title="People" />
      <LoadState result={data} retry={reload} what="people">
        {({ members, invites }) => (
          <>
            <section className="la-stack-2" aria-labelledby="members">
              <h2 id="members" className="la-overline">
                Admins and Referees
              </h2>
              <ul className="la-group">
                {members.map((member) => (
                  <li key={member.id} className="la-item">
                    <div className="la-item__body">
                      <span className="body-strong">
                        {member.name}
                        {member.user_id === myId ? " (you)" : ""}
                      </span>
                      <span className="caption la-muted">
                        {ROLE_LABELS[member.role]} · {member.email}
                      </span>
                    </div>
                    <ConfirmButton
                      label="Remove"
                      confirmLabel={`Remove ${member.name} as ${ROLE_LABELS[member.role]}`}
                      onConfirm={() =>
                        act(() =>
                          api.DELETE("/api/v1/clubs/{club_id}/members/{id}/", {
                            params: { path: { ...path, id: member.id } },
                          }),
                        )
                      }
                    />
                  </li>
                ))}
              </ul>
            </section>

            {invites.length > 0 && (
              <section className="la-stack-2" aria-labelledby="invites">
                <h2 id="invites" className="la-overline">
                  Invited, not signed up yet
                </h2>
                <ul className="la-group">
                  {invites.map((invite) => (
                    <li key={invite.id} className="la-item">
                      <div className="la-item__body">
                        <span className="body-strong">{invite.email}</span>
                        <span className="caption la-muted">{ROLE_LABELS[invite.role]}</span>
                      </div>
                      <ConfirmButton
                        label="Cancel"
                        confirmLabel={`Cancel invite for ${invite.email}`}
                        onConfirm={() =>
                          act(() =>
                            api.DELETE("/api/v1/clubs/{club_id}/invites/{id}/", {
                              params: { path: { ...path, id: invite.id } },
                            }),
                          )
                        }
                      />
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {error && <Banner status="cancelled" title={error} />}
            {notice && <Banner status="confirmed" title={notice} />}

            <InviteForm
              clubId={clubId}
              onInvited={(invite) => {
                setError(null);
                setNotice(
                  invite.accepted
                    ? `${invite.email} now has the ${ROLE_LABELS[invite.role]} role.`
                    : `Invited ${invite.email}. They get the ${ROLE_LABELS[invite.role]} role when they sign up with this email.`,
                );
                reload();
              }}
            />
          </>
        )}
      </LoadState>
    </main>
  );
}

function InviteForm({ clubId, onInvited }: { clubId: number; onInvited: (invite: Schemas["ClubInvite"]) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("referee");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function invite() {
    setBusy(true);
    let answer: Schemas["ClubInvite"] | undefined;
    const failed = await send(async () => {
      const result = await api.POST("/api/v1/clubs/{club_id}/invites/", {
        params: { path: { club_id: clubId } },
        body: { email, role },
      });
      answer = result.data;
      return result;
    });
    setBusy(false);
    setErrors(failed ?? NO_ERRORS);
    if (!failed && answer) {
      setEmail("");
      onInvited(answer);
    }
  }

  return (
    <form
      className="la-stack la-form"
      aria-label="Invite"
      onSubmit={(event) => {
        event.preventDefault();
        void invite();
      }}
    >
      <h2 className="la-overline">Invite</h2>
      <TextField
        label="Email"
        type="email"
        autoComplete="off"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        error={errors.fields.email}
      />
      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-field__label">As</legend>
        <div className="la-choices">
          {(["referee", "admin"] as const).map((value) => (
            <ChoiceChip key={value} pressed={role === value} onToggle={() => setRole(value)}>
              {ROLE_LABELS[value]}
            </ChoiceChip>
          ))}
        </div>
      </fieldset>
      {errors.general && <Banner status="cancelled" title={errors.general} />}
      <button type="submit" className="la-btn la-btn--primary la-btn--block" disabled={busy || !email.trim()}>
        Send invite
      </button>
    </form>
  );
}
