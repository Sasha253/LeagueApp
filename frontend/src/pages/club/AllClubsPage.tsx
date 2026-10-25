// All clubs: every Club in the app, for a superuser, who opens each one as its Admin
// (docs/DECISIONS.md). The API answers 403 to anyone else.

import { Link } from "react-router";
import { api } from "../../api/client";
import { ClubShortcuts } from "./ClubShortcuts";
import { LoadState, useLoad } from "./shared";

export function AllClubsPage() {
  const [clubs, retry] = useLoad(() => api.GET("/api/v1/clubs/"), "clubs");

  return (
    <main className="la-screen">
      <div className="la-stack-2">
        <Link className="la-btn la-btn--quiet la-back" to="/profile">
          Profile
        </Link>
        <h1 className="title-1">All clubs</h1>
      </div>
      <LoadState result={clubs} retry={retry} what="clubs" forbidden="Only a superuser can see every club.">
        {(list) =>
          list.length === 0 ? (
            <p className="body la-muted">No clubs yet.</p>
          ) : (
            <ul className="la-group">
              {list.map((club) => (
                <li key={club.id} className="la-item">
                  <div className="la-item__body">
                    <span className="body-strong">{club.name}</span>
                  </div>
                  <ClubShortcuts clubId={club.id} clubName={club.name} role="admin" />
                </li>
              ))}
            </ul>
          )
        }
      </LoadState>
    </main>
  );
}
