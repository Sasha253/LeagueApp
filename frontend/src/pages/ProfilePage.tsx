// Profile (design/src/ds/Screens.md, Shared 1, 2 and 5): how you use the app, your
// position and the Nights you get notifications for. Theme, payment methods and credit
// come with later chunks.

import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type Me, type Night, type Position } from "../api/client";
import { formErrors, unreachable, type FormErrors } from "../api/errors";
import { useAuth } from "../auth/AuthProvider";
import { Banner } from "../components/Banner";
import { ChoiceChip } from "../components/ChoiceChip";
import { StatusChip } from "../components/StatusChip";
import { WEEKDAYS_SHORT as WEEKDAYS } from "../format";
import { onInboxChanged } from "../push/events";
import { ClubShortcuts } from "./club/ClubShortcuts";
import { POSITIONS } from "./positions";

const ROLE_LABELS = { admin: "Admin", referee: "Referee" } as const;
const NO_ERRORS: FormErrors = { fields: {}, general: null };

type Draft = { plays: boolean; books: boolean; position: Position | null; nights: number[] };

const draftOf = (me: Me): Draft => ({
  plays: !!me.player,
  books: !!me.is_booking_user,
  position: me.player?.position ?? null,
  nights: me.player?.nights ?? [],
});

type NightsResult = { state: "loading" } | { state: "ok"; nights: Night[] } | { state: "error" };

function useNights(attempt: number): NightsResult {
  const [result, setResult] = useState<NightsResult>({ state: "loading" });
  useEffect(() => {
    let cancelled = false;
    setResult({ state: "loading" });
    api
      .GET("/api/v1/nights/")
      .then(({ data }) => {
        if (!cancelled) setResult(data ? { state: "ok", nights: data } : { state: "error" });
      })
      .catch(() => {
        if (!cancelled) setResult({ state: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);
  return result;
}

/** Nights grouped by club, in the order the API lists them. */
function byClub(nights: Night[]): { club: Night["club"]; nights: Night[] }[] {
  const groups = new Map<number, { club: Night["club"]; nights: Night[] }>();
  for (const night of nights) {
    const group = groups.get(night.club.id) ?? { club: night.club, nights: [] };
    group.nights.push(night);
    groups.set(night.club.id, group);
  }
  return [...groups.values()];
}

/** How many notifications are unread, or null until known. */
function useUnread(): number | null {
  const [unread, setUnread] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => onInboxChanged(() => setAttempt((n) => n + 1)), []);
  useEffect(() => {
    let cancelled = false;
    api
      .GET("/api/v1/inbox/summary/")
      .then(({ data }) => {
        if (!cancelled && data) setUnread(data.unread);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [attempt]);
  return unread;
}

export function ProfilePage() {
  const { state, setMe, endSession } = useAuth();
  const me = state.status === "signedIn" ? state.me : null;
  const [draft, setDraft] = useState<Draft | null>(me && draftOf(me));
  const [nightsAttempt, setNightsAttempt] = useState(0);
  const nights = useNights(nightsAttempt);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const unread = useUnread();

  if (!me || !draft) return null;

  const change = (next: Partial<Draft>) => {
    setDraft({ ...draft, ...next });
    setSaved(false);
  };
  const toggleNight = (id: number) =>
    change({
      nights: draft.nights.includes(id)
        ? draft.nights.filter((n) => n !== id)
        : [...draft.nights, id],
    });

  async function save() {
    if (!draft) return;
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const { data, error } = await api.PATCH("/api/v1/auth/me/", {
        body: {
          is_booking_user: draft.books,
          player:
            draft.plays && draft.position
              ? { position: draft.position, nights: draft.nights }
              : null,
        },
      });
      if (data) {
        setMe(data);
        setDraft(draftOf(data));
        setSaved(true);
      } else {
        setErrors(formErrors(error));
      }
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  const canSave = (draft.plays || draft.books) && (!draft.plays || draft.position !== null);

  return (
    <main className="la-screen">
      <div className="la-stack-2">
        <h1 className="title-1">Profile</h1>
        <p className="body">{me.name}</p>
        <p className="caption la-muted">{me.email}</p>
      </div>

      <ul className="la-group">
        <li>
          <Link className="la-item la-item--link" to="/inbox">
            <span className="la-item__body">
              <span className="body-strong">Inbox</span>
              <span className="caption la-muted">Confirmations, requests and updates</span>
            </span>
            {unread !== null && unread > 0 && <StatusChip status="pending">{`${unread} unread`}</StatusChip>}
          </Link>
        </li>
      </ul>

      {me.player && (
        <ul className="la-group">
          <li>
            <Link className="la-item la-item--link" to="/teams">
              <span className="la-item__body">
                <span className="body-strong">Teams</span>
                <span className="caption la-muted">Your Teams, find a team, request a Team</span>
              </span>
            </Link>
          </li>
          <li>
            <Link className="la-item la-item--link" to="/fixtures">
              <span className="la-item__body">
                <span className="body-strong">My fixtures</span>
                <span className="caption la-muted">Your Teams' matches, coming up and before</span>
              </span>
            </Link>
          </li>
        </ul>
      )}

      {me.is_booking_user && (
        <ul className="la-group">
          <li>
            <Link className="la-item la-item--link" to="/book">
              <span className="la-item__body">
                <span className="body-strong">Book a field</span>
                <span className="caption la-muted">Pick a day, field, time and hours</span>
              </span>
            </Link>
          </li>
          <li>
            <Link className="la-item la-item--link" to="/bookings">
              <span className="la-item__body">
                <span className="body-strong">My bookings</span>
                <span className="caption la-muted">Your bookings and their entry Barcodes</span>
              </span>
            </Link>
          </li>
        </ul>
      )}

      {me.is_superuser && (
        <ul className="la-group">
          <li>
            <Link className="la-item la-item--link" to="/clubs">
              <span className="la-item__body">
                <span className="body-strong">All clubs</span>
                <span className="caption la-muted">Open any club as its Admin</span>
              </span>
            </Link>
          </li>
        </ul>
      )}

      {me.club_roles.length > 0 && (
        <section className="la-stack-2" aria-labelledby="club-roles">
          <h2 id="club-roles" className="la-overline">
            At your clubs
          </h2>
          <ul className="la-group">
            {me.club_roles.map((role) => (
              <li key={`${role.club_id}-${role.role}`} className="la-item">
                <div className="la-item__body">
                  <span className="body-strong">{ROLE_LABELS[role.role]}</span>
                  <span className="caption la-muted">{role.club_name}</span>
                </div>
                <ClubShortcuts clubId={role.club_id} clubName={role.club_name} role={role.role} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <fieldset className="la-fieldset la-stack-2">
        <legend className="la-overline">How you use League App</legend>
        <div className="la-choices">
          <ChoiceChip pressed={draft.plays} onToggle={() => change({ plays: !draft.plays })}>
            I play
          </ChoiceChip>
          <ChoiceChip pressed={draft.books} onToggle={() => change({ books: !draft.books })}>
            I hire a field
          </ChoiceChip>
        </div>
      </fieldset>

      {draft.plays && (
        <>
          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Position</legend>
            <div className="la-choices">
              {POSITIONS.map(({ value, label }) => (
                <ChoiceChip
                  key={value}
                  pressed={draft.position === value}
                  onToggle={() => change({ position: value })}
                >
                  {label}
                </ChoiceChip>
              ))}
            </div>
            {errors.fields["player.position"] && (
              <span className="la-field__error">{errors.fields["player.position"]}</span>
            )}
          </fieldset>

          <fieldset className="la-fieldset la-stack-2">
            <legend className="la-overline">Nights</legend>
            <p className="caption la-muted">You only get notifications for the Nights you choose.</p>
            {nights.state === "loading" && (
              <p className="caption la-muted" role="status">
                Loading Nights
              </p>
            )}
            {nights.state === "error" && (
              <Banner status="cancelled" title="Couldn't load the Nights">
                <button
                  type="button"
                  className="la-btn la-btn--quiet"
                  onClick={() => setNightsAttempt((n) => n + 1)}
                >
                  Retry
                </button>
              </Banner>
            )}
            {nights.state === "ok" && nights.nights.length === 0 && (
              <p className="body la-muted">No Nights yet. Your club adds them.</p>
            )}
            {nights.state === "ok" &&
              byClub(nights.nights).map(({ club, nights: clubNights }) => (
                <div key={club.id} className="la-stack-2">
                  <p className="caption">{club.name}</p>
                  <div className="la-choices">
                    {clubNights.map((night) => (
                      <ChoiceChip
                        key={night.id}
                        pressed={draft.nights.includes(night.id)}
                        onToggle={() => toggleNight(night.id)}
                        label={`${WEEKDAYS[night.weekday]} at ${club.name}`}
                      >
                        {WEEKDAYS[night.weekday]}
                      </ChoiceChip>
                    ))}
                  </div>
                </div>
              ))}
            {errors.fields["player.nights"] && (
              <span className="la-field__error">{errors.fields["player.nights"]}</span>
            )}
          </fieldset>
        </>
      )}

      {errors.general && <Banner status="cancelled" title={errors.general} />}
      {saved && <Banner status="confirmed" title="Saved" />}

      <div className="la-stack">
        <button
          type="button"
          className="la-btn la-btn--primary la-btn--block"
          disabled={!canSave || busy}
          onClick={save}
        >
          Save
        </button>
        <button type="button" className="la-btn la-btn--secondary la-btn--block" onClick={endSession}>
          Log out
        </button>
      </div>

      <p className="caption la-muted">
        <Link className="la-link" to="/privacy">
          Privacy policy
        </Link>{" "}
        · Version {__APP_VERSION__} ({__APP_BUILD__})
      </p>
    </main>
  );
}
