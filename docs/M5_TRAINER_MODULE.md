# M5 — Trainer Module

The Trainer module gives trainers a dashboard and tools to manage their
assigned groups, puzzles, assignments, training sessions and attendance, and
to track student performance. Everything is backed by database records; no
values are hardcoded.

- Backend: `app/routers/trainer.py` (all routes under `/trainer`), services in
  `app/services/` (`trainer_access`, `trainer_service`, `puzzle_service`,
  `assignment_service`, `session_service`, `stats_service`,
  `chess_validation`), schemas in `app/schemas/` (`trainer`, `puzzle`,
  `assignment`, `session`).
- Frontend: pages in `frontend/src/pages/trainer/`, shared trainer code in
  `frontend/src/features/trainer/`. Routes and nav are registered through
  `src/pages/trainer/routes.jsx`, which the shared `AppRouter` loads for users
  whose role is `trainer`.

## 1. Features

| Area | What a trainer can do |
|---|---|
| Dashboard | Profile, summary cards (groups, students, active assignments, upcoming/completed sessions, puzzles created), 30‑day performance, upcoming schedule, recent assignments, group overview, recent student activity, recently completed sessions |
| Groups | List assigned groups (search, active filter, pagination); group detail with counts and next session; student list (search, sort by name/rating/joined); per‑student performance table; assignment history |
| Students | Profile, puzzles attempted/solved, accuracy, assignment completion, attendance, XP, streaks, badges, 12‑week progress chart, recent activity, assignment list |
| Puzzles | Browse/filter by difficulty, rating range, category, theme, status and ownership; create, edit, validate FEN + UCI solution live; attach category and themes; publish, unpublish, archive, restore |
| Assignments | Create with title, description, group, optional selected students, ordered puzzles, start and due date; save as draft or publish; edit drafts; publish, close, cancel; progress per student |
| Sessions | Schedule for an assigned group with title, description, learning objective, start/end time and meeting link; agenda view (upcoming/past/all); edit upcoming sessions; cancel; mark completed; roster; attendance |
| Profile | Update name, phone, specialization, experience, bio; request a password reset link |

## 2. Role policy and ownership rules

All rules are enforced in the backend services, not only in the UI.

- Every `/trainer/*` route requires the `trainer` role (`require_trainer`).
  Students **and admins** get `403`; missing or invalid tokens get `401`.
  Admins manage groups through the Admin module (M4).
- A trainer account also needs a `trainer_profiles` row, which an admin
  creates. Without one, every trainer route returns `403`.
- **Groups.** A trainer owns the groups whose `groups.trainer_id` is their
  trainer profile; admins set that assignment. Trainers cannot create
  groups, change membership or change roles.
- **Students.** A trainer can see a student only while that student is a
  member of one of the trainer's groups.
- **Other trainers' resources.** Groups, students, assignments and sessions
  that belong to another trainer return `404`, so their existence is not
  revealed.
- **Puzzles.** A trainer sees every *published* puzzle plus all of their own
  puzzles in any status. Only the author (`created_by_trainer_id`) may edit or
  change a puzzle's status. Library puzzles (seeded or imported, no author)
  and other trainers' published puzzles are read-only (`403` on change).
  Other trainers' drafts and archived puzzles are invisible (`404`).
- **Assignments and sessions** can target only the trainer's own *active*
  groups (an inactive group returns `409`).
- **Performance isolation.** Assignment and attendance metrics count only the
  requesting trainer's own assignments and sessions. If a student belongs to
  two trainers' groups, neither trainer sees the other's assignments or
  attendance. Puzzle attempts are the student's own practice and count for
  both.
- **Profile.** `PATCH /trainer/profile` forbids unknown fields. Sending `role`,
  `is_active` or `email` returns `422`, and nothing is changed.

## 3. Database changes

Migration `a5c1e7d2b934_trainer_module_columns` (revises `29dd76e3604b`) is
additive and reversible. No tables were added or duplicated.

| Column | Why the M2 schema could not support the feature |
|---|---|
| `puzzles.created_by_trainer_id` (nullable FK → `trainer_profiles`, `SET NULL`, indexed) | Puzzles had no owner, so "edit only puzzles you own" could not be enforced. NULL means a library puzzle. |
| `puzzles.status` (`draft`/`published`/`archived`, default `published`, check constraint, indexed) | No publish/archive lifecycle existed. Existing rows default to `published`, so current behaviour is unchanged. |
| `assignments.start_date` (+ check `due_date >= start_date`) | Only a due date existed; the requirement asks for a start date and date-order validation. |
| `class_sessions.learning_objective` (text) | Sessions had no field for a learning objective. |

Existing tables reused as-is: `groups`, `group_members`, `trainer_profiles`,
`student_profiles`, `puzzle_categories`, `puzzle_themes`,
`puzzle_theme_mappings`, `assignments`, `assignment_puzzles`,
`assignment_recipients`, `submissions`, `class_sessions`,
`session_attendance`, `puzzle_attempts`, `student_progress`, `student_badges`,
`badges`.

## 4. Puzzle validation

Implemented in `app/services/chess_validation.py` using `python-chess`.
`validate_puzzle_solution` holds the M2 rules: the FEN must parse and be a
legal position (`board.is_valid()`), the solution must not be empty, every
move must be valid UCI, and each must be legal when played in order. It is
shared with `scripts/seed.py`, so seed data and trainer puzzles follow the
same rules.

Trainer-authored puzzles go through `validate_trainer_puzzle`, which adds:

- The FEN must have all six fields. python-chess would otherwise silently
  fill in missing ones.
- The starting position must not already be checkmate, stalemate or another
  finished game.
- The line may not continue after the game has ended (e.g. a move after mate).
- At most 40 half-moves.
- The solution is normalized (lowercased, single spaces) and the FEN is
  stored in canonical form.

Further rules:

- `POST /trainer/puzzles/validate` runs the same checks without saving. The
  editor calls it as you type, so the UI never applies different rules from
  the server.
- Once a puzzle is used in an assignment or has attempts, its FEN and
  solution are **locked** (`409` on change), so recorded results stay
  meaningful. Rating, category, themes and explanation remain editable.
- New puzzles start as `draft`. Only `published` puzzles can be added to
  assignments.
- Categories and themes must exist (`422` otherwise), and duplicate theme ids
  are rejected. Taxonomy entries are reused from the existing tables; trainers
  attach them but do not create them.

## 5. Assignment workflow

```
draft ──publish──▶ published ──close──▶ completed
  │                    │
  └──────cancel────────┴──────────────▶ cancelled
```

- **Create:** pass `group_id` (an owned, active group), `puzzle_ids`
  (ordered, unique, published) and optionally `student_ids`. Omitting
  `student_ids` (or sending `null`) targets the whole group
  (`assignment_type='group'`). A list targets those members only
  (`'individual'`); every id must belong to the group (`422` otherwise).
- **Dates:** must include a UTC offset. `due_date >= start_date` is checked in
  the schema, the service and a DB constraint.
- **Drafts** may be saved empty. Only drafts can be edited (`409` otherwise).
  Changing the group without new selections resets the assignment to the
  whole group.
- **Publish** requires an active group, at least one puzzle, all puzzles
  still published, a due date in the future, and at least one recipient. For
  whole-group assignments, recipients are re-synced to the current members at
  publish time.
- **Duplicates:** duplicate ids in a request are rejected (`422`), and
  recipients are written as a set, backed by the
  `unique_assignment_student` constraint.

## 6. Session and attendance workflow

- Times must include a UTC offset and are stored in UTC. The UI converts
  between the trainer's local timezone (shown on the page) and UTC.
- **Scheduling:** the session must start in the future, end after its start,
  and last at most 8 hours. It must not overlap another of the trainer's
  scheduled or ongoing sessions (`409`).
- **Editing:** only upcoming `scheduled` sessions can be edited. The group of
  a scheduled session cannot change.
- **Status changes:** `cancel` works on scheduled/ongoing sessions.
  `complete` works on scheduled/ongoing sessions that have already started.
- **Attendance:**
  - Allowed once the session has started, and never for a cancelled session.
  - Accepted statuses: `present`, `late`, `absent`, `excused`. The schema's
    `scheduled` value means "not recorded" and cannot be submitted.
  - A student may appear only once per request (`422`), and only students on
    the roster are accepted. The roster is the current group members plus
    anyone already recorded.
  - Recording again updates the existing row (upsert), so with the
    `unique_session_student` constraint there is never more than one record
    per student per session.

## 7. Performance metrics

All metrics are computed by grouped queries in `app/services/stats_service.py`
(one query per metric family for any number of students, with no N+1
queries). Percentages are rounded to one decimal and are `null` (shown as
"—") when the denominator is zero, so "no data" is never shown as 0%.

| Metric | Calculation |
|---|---|
| Puzzles attempted | Distinct puzzles with at least one row in `puzzle_attempts` |
| Puzzles solved | Distinct puzzles with at least one attempt where `is_solved` |
| Accuracy | solved attempts ÷ all attempts × 100 (attempt level, so retries count) |
| Assignments received | The trainer's `published` or `completed` assignments where the student is a recipient (drafts and cancelled are excluded) |
| Assignment completed | Every puzzle of the assignment has a solved attempt **linked to that assignment** (`puzzle_attempts.assignment_id`) |
| Assignment completion rate | completed ÷ received × 100 |
| Attendance rate | (present + late) ÷ (present + late + absent) × 100 over the trainer's non-cancelled sessions; `excused` and unrecorded are excluded |
| XP, streaks | `student_progress.total_xp`, `current_streak`, `longest_streak` |
| Badges | Rows in `student_badges` (joined with `badges`) |
| Progress over time | Attempts and solves per ISO week (Monday, UTC) for the last 12 weeks; empty weeks are included as zero |
| Assignment progress (per student) | Distinct assignment puzzles solved ÷ puzzles in assignment. Status is `completed` when all are solved, `in_progress` with any attempt, otherwise `not_started`. Also shows the latest `submissions` row (status, score) if one exists. |
| Group / dashboard rates | Pooled: numerators and denominators are summed across students, then divided. Rates are not averaged. |
| Dashboard 30-day performance | Attempts, solves, accuracy and distinct active students for attempts in the last 30 days, across all students in the trainer's groups |

## 8. API reference

All list endpoints accept `page` (≥ 1) and `page_size` (1–100, default 20)
and return:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0 }
```

Errors use FastAPI's shape `{"detail": "..."}`; validation errors use the
standard 422 list.

| Method & path | Purpose |
|---|---|
| `GET /trainer/dashboard` | Dashboard data |
| `GET /trainer/profile` · `PATCH /trainer/profile` | View / update own profile |
| `GET /trainer/groups?search=&is_active=` | Assigned groups |
| `GET /trainer/groups/{id}` | Group detail and counts |
| `GET /trainer/groups/{id}/students?search=&sort=name\|-name\|rating\|-rating\|joined\|-joined` | Members |
| `GET /trainer/groups/{id}/assignments` | Assignment history |
| `GET /trainer/groups/{id}/performance` | Group and per-student metrics |
| `GET /trainer/students/{student_id}/performance` | Student profile and progress |
| `GET /trainer/puzzle-taxonomy` | Categories and themes |
| `GET /trainer/puzzles?search=&difficulty=&category_id=&theme_id=&rating_min=&rating_max=&status=&ownership=all\|mine\|library&sort=` | Puzzle list |
| `POST /trainer/puzzles/validate` | Dry-run FEN/solution validation |
| `POST /trainer/puzzles` · `GET` · `PATCH /trainer/puzzles/{id}` | Create / view / edit |
| `POST /trainer/puzzles/{id}/publish\|unpublish\|archive\|restore` | Status changes |
| `GET /trainer/assignments?status=&group_id=&search=&sort=` · `POST /trainer/assignments` | List / create |
| `GET` · `PATCH /trainer/assignments/{id}` | Detail / edit draft |
| `GET /trainer/assignments/{id}/progress` | Per-student progress |
| `POST /trainer/assignments/{id}/publish\|close\|cancel` | Status changes |
| `GET /trainer/sessions?scope=upcoming\|past\|all&status=&group_id=&search=&starts_after=&starts_before=` · `POST /trainer/sessions` | List / schedule |
| `GET` · `PATCH /trainer/sessions/{id}` | Detail with roster / edit |
| `POST /trainer/sessions/{id}/attendance` | Record attendance |
| `POST /trainer/sessions/{id}/cancel\|complete` | Status changes |

### Examples

Create a puzzle:

```http
POST /trainer/puzzles
{ "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "solution": "g6g7",
  "rating": 800, "difficulty": "beginner", "category_id": "…", "theme_ids": ["…"] }

201 { "id": "…", "status": "draft", "is_owner": true, "solution": "g6g7",
      "side_to_move": "white", "solution_locked": false, "themes": [ … ], … }

POST /trainer/puzzles  { "fen": "…", "solution": "g6e5" }
422 { "detail": "Illegal move g6e5 in position: 7k/8/5KQ1/8/8/8/8/8 w - - 0 1" }
```

Create and publish an assignment for two students:

```http
POST /trainer/assignments
{ "title": "Tactics week 1", "group_id": "…", "puzzle_ids": ["…", "…"],
  "student_ids": ["…", "…"], "start_date": "2026-11-03T09:00:00+05:30",
  "due_date": "2026-11-10T18:00:00+05:30", "publish": true }

201 { "id": "…", "status": "published", "assignment_type": "individual",
      "puzzle_count": 2, "recipient_count": 2, "completed_count": 0,
      "puzzles": [ … ], "recipients": [ … ], … }
```

Assignment progress:

```http
GET /trainer/assignments/{id}/progress
200 { "puzzles_total": 4, "recipients_total": 2, "completed_count": 1,
      "in_progress_count": 1, "not_started_count": 0, "completion_rate": 50.0,
      "average_completion_percent": 75.0, "is_overdue": false,
      "recipients": [ { "full_name": "Demo Student One", "puzzles_solved": 4,
                        "attempts": 5, "completion_percent": 100.0,
                        "status": "completed", "submission_status": null, … } ] }
```

Record attendance:

```http
POST /trainer/sessions/{id}/attendance
{ "records": [ { "student_id": "…", "status": "present" },
               { "student_id": "…", "status": "late", "remarks": "10 minutes" } ] }

200 { …session detail…, "attendance_summary":
      { "present": 1, "late": 1, "absent": 0, "excused": 0, "unrecorded": 0 } }
```

## 9. Frontend pages

| Route (hash) | Page |
|---|---|
| `#/trainer/dashboard` (alias `#/trainer`) | Dashboard |
| `#/trainer/groups` | My groups |
| `#/trainer/groups/:id?tab=students\|performance\|assignments` | Group detail, student list, group performance, assignment history |
| `#/trainer/students/:id` | Student performance |
| `#/trainer/puzzles` · `/new` · `/:id` · `/:id/edit` | Puzzle library, create, detail, edit |
| `#/trainer/assignments` · `/new` · `/:id` · `/:id/edit` | Assignment list, create, progress, edit draft |
| `#/trainer/sessions?scope=` · `/new` · `/:id` · `/:id/edit` | Session agenda, schedule, detail + attendance, edit |
| `#/trainer/profile` | Profile |

The pages use the shared API client (`src/api/client.js`), auth store, hash
router and `AppShell` from M6.

Trainer-specific UI lives in `src/features/trainer/components`:

- Data table that stacks into cards on phones
- Pagination
- Form fields with inline errors
- Confirmation dialog on native `<dialog>`
- Toasts
- Read-only FEN board
- Loading, empty and error states

All of them have accessible labels.

Styles (`src/features/trainer/trainer.css`) read the shared `--color-*`,
`--space-*` and `--radius` tokens with fallbacks and support dark mode. No new
dependencies were added.

## 10. Tests

Backend tests live in `backend/tests/test_trainer_*.py`. Fixtures are in
`backend/tests/trainer_fixtures.py`: each test runs in one transaction that
is rolled back, so nothing persists.

| File | Covers |
|---|---|
| `test_trainer_access.py` | Student/admin `403`, unauthenticated `401`, trainer without profile, group isolation, pagination, profile updates, role/status/email changes rejected |
| `test_trainer_puzzles.py` | Valid creation, invalid FEN, illegal/invalid UCI, play after mate, already-finished start position, validate endpoint, theme/category checks, unauthorized edits, library read-only, filters, status transitions, solution lock |
| `test_trainer_assignments.py` | Create/publish, selected students, foreign group, inactive group, students outside group, empty assignment, unpublished/unknown puzzles, dates (order, past due, naive), duplicate recipients, draft-only edits, cross-trainer isolation, progress calculation |
| `test_trainer_sessions.py` | Valid scheduling, invalid ranges, overlaps, foreign group, cross-trainer access, edit/cancel, recording attendance, duplicate prevention, attendance rules, list scopes |
| `test_trainer_performance.py` | Accuracy, completion and attendance calculations, `null` when there is no data, pooled group rates, isolation between trainers, dashboard counts |

Commands. Run the backend in Docker, because `.env` points at the `db`
service:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m pytest -q
docker compose exec backend python -m pytest -q tests/test_trainer_*.py

cd frontend
npm run lint
npm run build
```

## 11. Known limitations

- The M4 Admin module is not in the repository yet, so trainer accounts,
  trainer profiles, groups and memberships currently come from
  `scripts/seed.py` or direct database work.
- Email delivery is not configured (see `email_service.py`). The profile
  page's "send password reset link" calls the existing endpoint, but no
  email is sent yet.
- Assignment completion is based on solved puzzle attempts linked to the
  assignment. Students cannot create such attempts until the M6 Student
  module is in place.
- There is no manual `ongoing` transition; sessions go from `scheduled`
  straight to `completed` or `cancelled`.
- The weekly progress chart buckets by UTC weeks.
