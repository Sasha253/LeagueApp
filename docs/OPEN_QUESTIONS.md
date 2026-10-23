# Open questions

Questions met during unattended runs, with the choice made. Move the answers you agree
with into docs/DECISIONS.md.

## Chunk 4: Import Nights and Divisions from Excel

None. Every question this chunk raised was already answered and is recorded in
docs/DECISIONS.md under "2026-10-23: Import Nights and Divisions (chunk 4)".

## Chunk 5: Teams (backend)

None. Every question this chunk raised was already answered and is recorded in
docs/DECISIONS.md under "2026-10-23: Teams (chunk 5)".

- **Joining a Team after its Season has ended (review).** Question: may a Player ask to
  join, or a Captain accept a Player into, a Team whose Season has ended? Choice: no, 409
  "This Season has ended." Why: a Team can't be requested for an ended Season, and a
  membership in a finished Season means nothing for fixtures or payments. If the answer
  differs: remove the `_season_ended` checks in `backend/teams/rules.py` and the test
  `test_no_joining_a_team_once_its_season_has_ended`.

## Chunk 6: Teams (UI)

- **No Team mockups in design/.** Question: which layout do the Team screens use? Choice:
  built from design/src/ds/Screens.md (Player 4 and 5, Captain 1 to 3, Admin 3) with the
  existing `la-` components, plus one proposed SelectableRow. Why: the screen list
  describes them and the components exist. If the answer differs: restyle
  `frontend/src/pages/teams/`; no API change.
- **How a user reaches the Team screens.** Question: there is no tab bar yet; where do the
  screens hang? Choice: Profile links Players to Teams and Admins to Team requests. Why:
  smallest change that makes them reachable; the tab bar is its own piece of work. If the
  answer differs: add the tab bar (Teams / My team / Requests tabs) and drop the Profile
  links.
- **Division filter in Find a team.** Question: which Divisions to offer, given the Night
  list carries no Divisions? Choice: after a Night is picked, the Divisions of that Night's
  Teams in the results. Why: no API change, and only Divisions with Teams can match. If
  the answer differs: add Divisions to `GET /api/v1/nights/` and list them all.
- **Telling a Captain their Team was declined.** Question: should the Captain see a
  declined Team and the Admin's reason in the app? Choice: no, the chunk 5 API leaves
  declined Teams out of "my Teams", and the reason is shown only on the Admin's screen.
  Why: conservative, no API change in a UI chunk; notifications (chunks 9 and 10) are the
  place to tell them. If the answer differs: include declined Teams with `decline_reason`
  in `GET /api/v1/me/teams/` and show them on Teams.
