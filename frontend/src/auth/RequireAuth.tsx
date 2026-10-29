import { Navigate, Outlet } from "react-router";
import { Banner } from "../components/Banner";
import { useAuth } from "./AuthProvider";

/** Shows its routes only to a signed-in user; everyone else goes to Log in. */
export function RequireAuth() {
  const { state, retry, backToAdmin } = useAuth();

  if (state.status === "loading") return <p className="sr-only" role="status">Loading</p>;
  if (state.status === "signedOut") return <Navigate to="/login" replace />;
  if (state.status === "unreachable") {
    return (
      <main className="la-screen">
        <Banner status="cancelled" title="Can't reach League App">
          Check your connection and try again.
          <button type="button" className="la-btn la-btn--quiet" onClick={retry}>
            Retry
          </button>
        </Banner>
      </main>
    );
  }
  return (
    <>
      {state.me.is_test_account && (
        // Over every screen, so a superuser always knows they're a test user.
        <div className="la-test-user">
          <Banner status="info" title={`Signed in as ${state.me.name}`}>
            A test user, from your superuser account.
            <button type="button" className="la-btn la-btn--quiet la-btn--sm" onClick={backToAdmin}>
              Back to superuser
            </button>
          </Banner>
        </div>
      )}
      <Outlet />
    </>
  );
}
