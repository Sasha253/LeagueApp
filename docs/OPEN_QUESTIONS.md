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
