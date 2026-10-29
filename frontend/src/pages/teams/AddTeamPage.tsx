// Add a Team (docs/DECISIONS.md): the Admin adds a confirmed Team to a Division for a
// Season, with its Captain, a Player in League App found by email. The API checks the league
// fee, the Division's room and the Captain, and charges the fee.

import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { ChoiceChip } from "../../components/ChoiceChip";
import { TextField } from "../../components/TextField";
import { WEEKDAYS_SHORT } from "../../format";
import { LoadState, NO_ERRORS, useClub, useLoad } from "../club/shared";
import { openingSeason } from "../finance/shared";
import { ScreenHeader } from "./shared";

export function AddTeamPage() {
  const { clubId, clubName } = useClub();
  const navigate = useNavigate();
  const path = { club_id: clubId };
  const [seasons, reloadSeasons] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/seasons/", { params: { path } }),
    `seasons-${clubId}`,
  );
  const [nights, reloadNights] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/nights/", { params: { path } }),
    `nights-${clubId}`,
  );
  const [season, setSeason] = useState<number | null>(null);
  const [division, setDivision] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [captain, setCaptain] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function save(seasonId: number) {
    if (division === null) return;
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const { data, error } = await api.POST("/api/v1/clubs/{club_id}/teams/", {
        params: { path },
        body: { season: seasonId, division, name, captain_email: captain },
      });
      if (data) navigate(`/clubs/${clubId}/teams/${data.id}`);
      else setErrors(formErrors(error));
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Add a Team" back={{ label: "Club home", to: `/clubs/${clubId}` }} caption={clubName} />
      <LoadState result={seasons} retry={reloadSeasons} what="Seasons">
        {(seasonList) => (
          <LoadState result={nights} retry={reloadNights} what="Nights and Divisions">
            {(nightList) => {
              const chosen = season ?? openingSeason(seasonList);
              const divisions = nightList.flatMap((n) => n.divisions.map((d) => ({ ...d, weekday: n.weekday })));
              if (chosen === null || divisions.length === 0) {
                return (
                  <Banner status="pending" title="Nothing to add a Team to yet">
                    A Team needs a Season and a Division. Add them in Club setup first.
                  </Banner>
                );
              }
              return (
                <form
                  className="la-stack la-form"
                  aria-label="New Team"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void save(chosen);
                  }}
                >
                  <fieldset className="la-fieldset la-stack-2">
                    <legend className="la-overline">Season</legend>
                    <div className="la-choices">
                      {seasonList.map((s) => (
                        <ChoiceChip key={s.id} pressed={chosen === s.id} onToggle={() => setSeason(s.id)}>
                          {s.name}
                        </ChoiceChip>
                      ))}
                    </div>
                    {errors.fields.season && <span className="la-field__error">{errors.fields.season}</span>}
                  </fieldset>
                  <fieldset className="la-fieldset la-stack-2">
                    <legend className="la-overline">Division</legend>
                    <div className="la-choices">
                      {divisions.map((d) => (
                        <ChoiceChip key={d.id} pressed={division === d.id} onToggle={() => setDivision(d.id)}>
                          {`${WEEKDAYS_SHORT[d.weekday]} · ${d.name}`}
                        </ChoiceChip>
                      ))}
                    </div>
                    {errors.fields.division && <span className="la-field__error">{errors.fields.division}</span>}
                  </fieldset>
                  <TextField
                    label="Team name"
                    value={name}
                    placeholder="Red Lions"
                    onChange={(event) => setName(event.target.value)}
                    error={errors.fields.name}
                  />
                  <TextField
                    label="Captain's email"
                    type="email"
                    value={captain}
                    help="A Player in League App. They're in the Team at once, as its Captain."
                    onChange={(event) => setCaptain(event.target.value)}
                    error={errors.fields.captain_email}
                  />
                  {errors.general && <Banner status="cancelled" title={errors.general} />}
                  <button
                    type="submit"
                    className="la-btn la-btn--primary la-btn--block"
                    disabled={busy || division === null || !name.trim() || !captain.trim()}
                  >
                    Add Team
                  </button>
                </form>
              );
            }}
          </LoadState>
        )}
      </LoadState>
    </main>
  );
}
