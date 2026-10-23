# Chunk 5: Teams (backend)

Unattended run, 2026-10-23. PRD: Captain and Admin rows of the roles table.

## Plan

The chunk was already built in the working tree, uncommitted (chunk 4 is committed). This
run checks it against the chunk prompt, fixes what is wrong, and commits it.

- Models (`backend/teams/models.py`): Team (club, Season, Division, name, captain, status
  requested/active/declined, who asked and decided), TeamMembership (joined_at, left_at:
  history kept, rejoining opens a new row), JoinRequest (pending/accepted/declined/
  withdrawn). `Division.max_teams` (clubs migration 0004), set by the Admin.
- Rules (`backend/teams/rules.py`): every change in a transaction, locking the Player and
  Division it checks. One Team per Player per Division and Season; no Team until the
  Division has a league fee; Division full at `max_teams` active Teams; names unique per
  Division and Season, case-insensitive.
- Endpoints, under /api/v1/:
  - Player: `GET/POST teams/` (search, request a Team), `GET teams/{id}/`,
    `POST teams/{id}/join/`, `POST teams/{id}/leave/`, `GET teams/{id}/members/`,
    `GET me/teams/`, `GET me/join-requests/`, `GET seasons/`,
    `GET seasons/{id}/divisions/`, `POST join-requests/{id}/withdraw/`.
  - Captain: `GET teams/{id}/join-requests/`, `POST join-requests/{id}/accept|decline/`.
  - Admin (own Club only): `GET clubs/{club_id}/teams/`, `GET clubs/{club_id}/teams/{id}/`,
    `POST .../confirm/`, `POST .../decline/`, `POST .../captain/`.
  - `GET auth/me/` gains `captain_of`.
- Permissions: `IsTeamCaptain` in `backend/accounts/permissions.py`; Admin views use
  `ClubAdminMixin`.
- Tests: `backend/teams/tests/test_team_requests.py`, `backend/teams/tests/test_joining.py`.

Later (not in this chunk): Teams screens (chunk 6); carrying a Team into the next Season;
removing Players from a Team; reading `max_teams` in the Nights and Divisions import;
notifications for Team and join decisions.

## Result

Built: everything in the chunk prompt (see the plan). Fixed in this run: a Team's detail
page counted Players wrongly (N players showed as N squared for an active Team), because
the "Teams I'm in" filter joined memberships a second time after the count annotation. It
now uses an `Exists` subquery; regression test
`test_a_teams_page_counts_each_player_once`.

Not built: the Later list above.

By hand: nothing.

Checks: make test 159 passed; make lint clean; npm test 70 passed (15 files);
npm run build ok.

## Review (fix: chunk 5 review)

Independent review of ecf96f9 against the chunk prompt and CLAUDE.md.

Checked and fine: Admin views are limited to their own Club (`ClubAdminMixin` filters on
`club_id`, `IsClubAdmin` guards the URL); a Team's Club comes from its Season and its
Division must be in that Club; Captain is checked on the record (`IsTeamCaptain`), never
stored as a role; `max_teams` is data on the Division, the league fee is read from data
and money stays Decimal; no ledger, notification or UI code (those are later chunks);
`npm run gen:api` gives no diff, so the frontend types match the API.

Fixed:
- A Player could ask to join, and a Captain could accept a Player into, a Team whose
  Season had ended, though a Team can't be requested for an ended Season. Both now
  return 409 "This Season has ended." Test:
  `test_no_joining_a_team_once_its_season_has_ended`.
- Test gap: nothing showed that an Admin of another Club can't reach a Team through
  their own Club's URL. Added
  `test_an_admin_cannot_reach_another_clubs_team_through_their_own_club` (404 on detail,
  confirm, decline and captain).

Noted, not changed: `GET seasons/` and `GET seasons/{id}/divisions/` let in any signed-in
user, not only Players. They show nothing private (Season names and dates, Division fees
and counts), so they were left as they are.

Checks after the review: make test 161 passed; make lint clean; npm test 70 passed
(15 files); npm run build ok.
