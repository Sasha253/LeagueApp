// Log in as: the test users a superuser can sign in as, one per role at each club, to see
// the app as that role does (docs/DECISIONS.md). The API answers 403 to anyone else.

import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { Banner } from "../components/Banner";
import { LoadState, useLoad } from "./club/shared";

export function TestUsersPage() {
  const { startTestSession } = useAuth();
  const navigate = useNavigate();
  const [testers, retry] = useLoad(() => api.GET("/api/v1/auth/test-users/"), "test-users");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  async function logInAs(id: number, name: string) {
    setBusy(true);
    setFailed(null);
    try {
      const { data } = await api.POST("/api/v1/auth/test-users/{id}/login/", {
        params: { path: { id } },
      });
      if (!data) return setFailed(name);
      await startTestSession({ access: data.access, refresh: data.refresh }, data.user);
      navigate("/profile", { replace: true });
    } catch {
      setFailed(name);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="la-screen">
      <div className="la-stack-2">
        <Link className="la-btn la-btn--quiet la-back" to="/profile">
          Profile
        </Link>
        <h1 className="title-1">Log in as</h1>
        <p className="caption la-muted">
          Test users have no password: only a superuser can sign in as them. Go back from the
          bar at the top.
        </p>
      </div>
      {failed && <Banner status="cancelled" title={`Couldn't sign in as ${failed}`} />}
      <LoadState
        result={testers}
        retry={retry}
        what="test users"
        forbidden="Only a superuser can sign in as a test user."
      >
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No test users yet. Add them with make_test_users.</p>
          ) : (
            <ul className="la-group">
              {list.map((tester) => (
                <li key={tester.id} className="la-item">
                  <div className="la-item__body">
                    <span className="body-strong">{tester.name}</span>
                    <span className="caption la-muted">{tester.roles.join(" · ")}</span>
                  </div>
                  <button
                    type="button"
                    className="la-btn la-btn--quiet la-btn--sm"
                    disabled={busy}
                    aria-label={`Log in as ${tester.name}`}
                    onClick={() => logInAs(tester.id, tester.name)}
                  >
                    Log in
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
