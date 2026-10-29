// Club setup (design/src/ds/Screens.md, Admin 8, FR-42): where a Club's Admin reaches its
// settings, Seasons, Nights and Divisions, Fields and people, and the Excel import.

import { Link } from "react-router";
import { api } from "../../api/client";
import { Banner } from "../../components/Banner";
import { LoadState, SetupHeader, useClub, useLoad } from "./shared";
import { SETTING_LABELS } from "./ClubSettingsPage";

const SECTIONS = [
  { path: "settings", title: "Settings", detail: "Fees, cutoffs, booking policy, payments" },
  { path: "seasons", title: "Seasons", detail: "When each Season runs" },
  { path: "nights", title: "Nights and Divisions", detail: "Minimum players and Division fees" },
  { path: "fields", title: "Fields", detail: "Pitches and their Referees" },
  { path: "people", title: "People", detail: "Admins and Referees" },
  { path: "import", title: "Import from Excel", detail: "Seasons, Nights and Divisions, and Fixtures" },
];

export function ClubSetupPage() {
  const { clubId } = useClub();
  const [settings, retry] = useLoad(
    () => api.GET("/api/v1/clubs/{club_id}/settings/", { params: { path: { club_id: clubId } } }),
    `settings-${clubId}`,
  );

  return (
    <main className="la-screen">
      <SetupHeader title="Club setup" back="home" />
      <LoadState result={settings} retry={retry} what="club setup">
        {({ missing }) => (
          <>
            {missing.length > 0 && (
              <Banner status="pending" title="Set your fees">
                Still to set: {missing.map((name) => SETTING_LABELS[name] ?? name).join(", ")}.
              </Banner>
            )}
            <ul className="la-group">
              {SECTIONS.map((section) => (
                <li key={section.path}>
                  <Link className="la-item la-item--link" to={`/clubs/${clubId}/setup/${section.path}`}>
                    <span className="la-item__body">
                      <span className="body-strong">{section.title}</span>
                      <span className="caption la-muted">{section.detail}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </LoadState>
    </main>
  );
}
