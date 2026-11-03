# M6 — Student Module

The student portal: dashboard, assignments, interactive puzzle solving with
server-side verification, groups, class schedule, attendance, progress and
gamification. Every rule below is enforced by the backend; the frontend only
mirrors it.

## Features

| Area | What a student can do |
|---|---|
| Dashboard | See their next assignment, assignment counts by status, upcoming classes, recent puzzle attempts, puzzles solved, accuracy, XP, streak, badges and the next milestone. |
| Profile | View account, student and trainer details and group memberships; edit name, phone, photo URL, language and date of birth. |
| Groups | List their groups (trainer, member count, upcoming classes) and open a group's classes and assignments. Other members are counted, never listed. |
| Assignments | Filter by not started / in progress / overdue / completed, read instructions, see per-puzzle status, progress, points and submission/feedback, resume where they left off. |
| Puzzles | Solve on an interactive board with legal-move highlighting, promotion picker, move history, review arrows, restart, and solved/failed feedback with XP and badges. |
| Classes | Upcoming and past classes, class details and meeting link, their own attendance. |
| Attendance | Their own attendance history with a summary and rate. |
| Progress | Attempts, solved puzzles, accuracy, average solve time, assignment completion, XP per day (30 days), theme and difficulty breakdowns, activity feed, metric definitions. |
| XP and badges | XP total, streaks, recent XP events, next milestone, full badge collection (earned and locked). |

## API

All routes are under `/student`, require a valid access token with the
`student` role (401 without/with an invalid token, 403 for other roles), and
operate only on the caller's `StudentProfile`. A student account without a
profile gets 404 *"Your student profile has not been set up yet"* from data
routes; `GET /student/profile` still works. Lists return
`{items, total, page, page_size, pages}` and accept `page` / `page_size` (max 100).

| Method | Path | Notes |
|---|---|---|
| GET | `/student/dashboard` | Aggregated dashboard. |
| GET | `/student/profile` | Account, student info, trainer, groups. |
| PATCH | `/student/profile` | Only `full_name`, `phone`, `avatar_url`, `language`, `date_of_birth`; any other field is 422. |
| GET | `/student/groups` | Paginated. |
| GET | `/student/groups/{group_id}` | 404 unless a member. |
| GET | `/student/assignments?status=` | `pending`, `in_progress`, `completed`, `overdue`. |
| GET | `/student/assignments/{id}` | Instructions, progress, submission, puzzles. |
| GET | `/student/assignments/{id}/progress` | Progress only. |
| GET | `/student/assignments/{id}/puzzles` | Puzzle list with per-puzzle status. |
| GET | `/student/puzzles/{id}?assignment_id=` | Position + legal moves; solution only after solving. |
| POST | `/student/puzzles/{id}/attempts` | `{assignment_id, moves[], time_taken_seconds?}`. |
| GET | `/student/sessions?scope=` | `upcoming`, `past`, `all`. |
| GET | `/student/sessions/{id}` | 404 unless the student may see it. |
| GET | `/student/attendance` | Own records + `summary`. |
| GET | `/student/gamification` | XP, streaks, badges, next milestone. |
| GET | `/student/badges` | All badges with `earned` / `earned_at`. |
| GET | `/student/progress` | Metrics and breakdowns, with `metric_definitions`. |
| GET | `/student/activity` | Paginated puzzle attempt history. |

There are no write routes for assignments, attendance, XP, badges or progress;
`PUT`/`PATCH`/`POST`/`DELETE` on them return 405.

## Visibility rules (data isolation)

* **Assignments** — visible only when the student is an `assignment_recipients`
  row, the assignment is `published` or `completed` (closed), and its
  `start_date`, if set, has passed. Drafts and cancelled assignments are hidden.
* **Puzzles** — only through a visible assignment that contains them, so the
  puzzle detail and attempt routes require `assignment_id`.
* **Sessions** — sessions of the student's groups, plus any session with an
  attendance row for the student (individual lessons).
* **Groups** — membership only; other students' names and attendance remarks
  are never returned.
* Anything not visible returns **404 with the same message as a missing ID**,
  so another student's IDs cannot be confirmed by probing.

Implemented in `app/services/student_service.py`; every query filters by the
caller's `StudentProfile.id`. Lists use grouped queries (no N+1).

## Puzzle-solving workflow

Solution format (from the seed, unchanged): space-separated UCI. The first
move is the student's, from the stored FEN's side to move; moves then
alternate with the opponent's forced replies, e.g. `f1c4 d5c4 b3c4`.

1. `GET /student/puzzles/{id}` returns the FEN, board orientation (side to
   move), number of student moves required and **the legal moves of the
   position, computed by python-chess**. The solution is withheld.
2. The board only lets the student play moves from that legal-move list, so
   check, pins, castling rights, en passant and promotion are exactly the
   backend's rules. Promotions open a piece picker.
3. After each move the frontend posts **all of the student's moves so far**.
   The backend replays them from the stored FEN (`app/services/puzzle_solver.py`):
   * a malformed or illegal move, or more moves than the line needs → **422**,
     nothing stored;
   * a correct prefix → `in_progress` with the opponent's reply and the new
     legal moves, **nothing stored**;
   * the first wrong move → `failed`, one `PuzzleAttempt(is_solved=false)` stored;
   * the full line, or **any move that delivers checkmate** (alternative mates
     are accepted) → `solved`, one `PuzzleAttempt(is_solved=true)` stored.
4. On `solved` the response includes the SAN solution, the explanation, XP and
   badges awarded and the updated assignment progress.
5. Invalid stored puzzle data (bad FEN, illegal or empty line) → 422 on both
   detail and attempt routes.
6. A closed assignment (`status = completed`) is read-only → 409 on attempts.

Because a wrong move ends the attempt, moves cannot be taken back; the arrows
only review earlier positions and **Restart** begins a new attempt. Each wrong
guess is recorded, so guessing to discover the solution shows up in accuracy
and in the trainer's view.

## Assignment progress

Calculated from stored rows, never from client input:

* `total_puzzles` / `total_points` — `assignment_puzzles` rows.
* `completed_puzzles` / `earned_points` — assignment puzzles that have a solved
  `puzzle_attempts` row **linked to this assignment** for this student.
* `completion_percent` = completed / total × 100 (one decimal).
* Status: `completed` when every puzzle is solved → otherwise `overdue` if the
  due date has passed → `in_progress` if any attempt exists → `pending`.
  Late work is accepted and moves an overdue assignment to completed.
* When an attempt completes the assignment, a `submissions` row
  (`attempt_number 1`, `status submitted`, `score = earned points`) is created
  once, for the trainer to grade. Students cannot submit manually.

## XP, badges and streaks

Rules live in `app/services/xp_service.py` and `streak_service.py`, shared
with `scripts/seed.py` (the values are the M2 seed's, moved, not changed):

* **10 XP** the first time a student solves a puzzle (any assignment).
  Re-solving earns nothing; `already_solved` is returned.
* Badges are awarded when a `student_progress` counter reaches its threshold
  (`first-puzzle-solved` 1, `three-puzzles-solved` 3, `first-game-played` 1),
  once each (unique constraint), and grant their `xp_reward` once.
* XP events are unique per (student, source); the student's `student_progress`
  row is locked (`SELECT … FOR UPDATE`) while an attempt is recorded, so
  concurrent submissions cannot award XP twice.
* `daily_activity` is upserted per UTC day (attempted, solved, XP).
* **Current streak** = consecutive UTC activity days ending today or
  yesterday; after a missed day it is 0. Longest streak never decreases.
* There is no XP-based level in the data model; the "level" shown is the
  student profile's skill level set by the academy.
* Next milestone = the unearned badge with the largest fraction already
  reached (ties: fewest steps left, then puzzle badges).

## Metrics

* Puzzles attempted / solved — distinct puzzles with ≥1 attempt / solved attempt.
* Accuracy — solved attempts ÷ all attempts × 100.
* Average solve time — mean `time_taken_seconds` of solved attempts.
* Assignment completion — completed ÷ visible assignments × 100.
* Attendance rate — (present + late) ÷ (present + late + absent); excused and
  not-yet-recorded classes are excluded.
* Percentages are `null` when the denominator is 0.

## Frontend

No new dependencies. Hash router (`src/routes/router.jsx`), token handling
with refresh-and-retry in `src/api/client.js` (access token in memory,
refresh token in `localStorage`), `useAuth()` in `src/store/authStore.js`,
`useApi()` in `src/hooks/useApi.js`. Shared UI components are in `src/components/ui`,
the board in `src/components/chess/Board.jsx` (keyboard: arrow keys move
between squares, Enter selects/moves, Escape clears). Student pages are in
`src/pages/student`, and `routes.js` lists them. Admin and trainer accounts are routed to their own
portals.

## Testing

```bash
docker compose exec backend python -m pytest -q          # whole suite
docker compose exec backend python -m pytest -q tests/test_student_api.py tests/test_student_puzzles.py
cd frontend && npm run lint && npm run build
```

Student tests (`tests/test_student_*.py`, fixtures in `tests/student_world.py`)
run inside one rolled-back connection transaction and build their own academy
(trainer, two students, group, puzzles, assignments, sessions), so they never
depend on or modify existing data.
