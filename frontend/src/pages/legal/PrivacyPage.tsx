// The privacy policy, open without signing in (the stores ask for it inside the app, and
// Sign up links to it). The text comes from the API (backend/core/legal.py), the same text
// as the public /privacy/ page the store listings link to.

import { Link, useLocation, useNavigate } from "react-router";
import { api } from "../../api/client";
import { formatDate } from "../../format";
import { LoadState, useLoad } from "../club/shared";

/** "2026-10-24" → "Sat 24 Oct 2026": a policy date needs its year. */
function longDate(isoDate: string): string {
  return `${formatDate(isoDate)} ${isoDate.slice(0, 4)}`;
}

export function PrivacyPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [policy, reload] = useLoad(() => api.GET("/api/v1/legal/privacy/"), "privacy");
  // Opened straight from a link there is nothing to go back to: go to the start instead.
  const opened = location.key === "default";

  return (
    <main className="la-screen">
      <div className="la-stack-2">
        {opened ? (
          <Link className="la-btn la-btn--quiet la-back" to="/">
            League App
          </Link>
        ) : (
          <button type="button" className="la-btn la-btn--quiet la-back" onClick={() => void navigate(-1)}>
            Back
          </button>
        )}
        <h1 className="title-1">Privacy policy</h1>
      </div>
      <LoadState result={policy} retry={reload} what="the privacy policy">
        {(data) => (
          <article className="la-stack">
            <p className="caption la-muted">
              League App, run by {data.operator}. Last updated {longDate(data.updated_on)}.
            </p>
            {data.sections.map((section) => (
              <section key={section.heading} className="la-stack-2">
                <h2 className="headline">{section.heading}</h2>
                {section.paragraphs.map((paragraph) => (
                  <p key={paragraph} className="body">
                    {paragraph}
                  </p>
                ))}
              </section>
            ))}
            {data.contact_email && (
              <p className="body">
                Privacy questions and requests:{" "}
                <a className="la-link" href={`mailto:${data.contact_email}`}>
                  {data.contact_email}
                </a>
              </p>
            )}
            <p className="caption la-muted">
              Version {__APP_VERSION__} ({__APP_BUILD__})
            </p>
          </article>
        )}
      </LoadState>
    </main>
  );
}
