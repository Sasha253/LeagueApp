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

## Chunk 7: Fixtures and Admin fixture import

- **Which status moves are allowed.** Question: the PRD names the stages of a match but not
  every move between them. Choice: the table in `backend/fixtures/lifecycle.py`.
  Cancelled and played are final. A friendly needs the friendly-eligible flag. A reschedule
  may move confirming or ready back to scheduled, or ready back to confirming. One team out
  goes only to replacement offered, friendly or cancelled. Why: it follows the PRD flows
  (FR-1 to FR-18) and refuses anything they don't describe. If the answer differs: change
  `TRANSITIONS`. The parametrised test covers every pair.
- **When a re-imported row is the same Fixture.** Question: what makes a row match a
  Fixture the club already has? Choice: the same Division, Home, Away and kick-off. A
  re-import can change only Friendly eligible. A row for that Fixture on another pitch is an
  error ("reschedule it instead"). The import never moves or deletes a Fixture. Why:
  re-importing must not duplicate, and moving a match notifies people (FR-7 to FR-9), which
  the import doesn't do. If the answer differs: let `fixtures/imports.py` update the pitch
  or time once the reschedule chunk can notify.
- **Kick-off checks.** Question: which kick-offs can be imported? Choice: only kick-offs that
  are still to come, inside the Season's dates, and on the weekday of the Division's Night.
  Seasons that have ended take no imports. Why: a past or off-Night Fixture would trigger
  checkpoints at the wrong time or not at all, and is most likely a typo. If the answer
  differs: drop the checks in `plan()`; the model allows any kick-off.
- **Which Teams can play.** Question: may a Fixture name a Team still waiting for the Admin,
  or a Team of another Division? Choice: no. Both Teams must be confirmed (active) Teams of
  the row's Division in the chosen Season. Why: only confirmed Teams play league matches.
  If the answer differs: relax the Team lookup in `plan()`.
- **Clashes.** Question: when do two Fixtures clash? Choice: when they share a pitch, or a
  Team, at exactly the same kick-off, among Fixtures that aren't cancelled. The database
  also refuses two Fixtures on one pitch at one kick-off. Why: the PRD gives no match
  length, so overlaps can't be judged. If the answer differs: add a match length to
  ClubSettings (data, not code) and check overlaps.
- **Dates in the file.** Question: which date forms are read? Choice: 2026-10-27, 27/10/2026
  (day first, never month first), 27 Oct 2026 and Tue 27 Oct 2026, always with the year.
  Excel date and time cells are read as they are. Times are 24-hour in South African time.
  Why: day first is how South Africa writes dates; anything ambiguous is refused. If the
  answer differs: add forms to `parse_date`.
- **Who sees Fixtures.** Question: who can see which Fixtures? Choice: a club's Admins see
  all its Fixtures, filtered by Season and Night, and only Seasons that haven't ended unless
  a Season is picked. A Player or Captain sees the Fixtures of the Teams they are in now,
  including cancelled ones. A Player who left a Team stops seeing its Fixtures. No one else
  sees them. Referees get their pitch's matches with the Tonight view (later). Why: this is
  the smallest view that covers the screens. Fixtures name Teams, so they aren't made
  public. If the answer differs: widen the querysets in `backend/fixtures/views.py`.
- **When friendly-eligible can change.** Question: until when can the Admin change the flag?
  Choice: while the Fixture is scheduled, confirming, ready, one team out or replacement
  offered. After that the answer is 409. The flag can also be set by the import. Who set it
  and when is kept. Why: once a match is a friendly, cancelled or played, changing the flag
  means nothing. If the answer differs: change `FLAG_OPEN` in `lifecycle.py`.
