# M4 — Admin Module

The Admin module lets academy administrators manage accounts, trainers,
students, groups and puzzles, and oversee assignments, sessions, attendance,
games and gamification. Every figure is read from the database; nothing is
hardcoded or estimated.

- Backend: `app/routers/admin.py` (all routes under `/admin`), services
  `app/services/admin_service.py` (users, trainers, students, groups) and
  `app/services/admin_reports_service.py` (dashboard, puzzles, oversight,
  reports), schemas in `app/schemas/admin.py`.
- Frontend: pages in `frontend/src/pages/admin/`, shared admin code in
  `frontend/src/features/admin/`. Routes and nav are registered through
  `src/pages/admin/routes.jsx`, which the shared `AppRouter` loads for users
  whose role is `admin`. Admin pages reuse the Trainer module's component kit
  (`features/trainer/components`) instead of duplicating it.
- Tests: `backend/tests/test_admin.py`.

## 1. Features

| Area | What an admin can do |
|---|---|
| Dashboard | Summary cards (users by role and status, groups, puzzles, assignments, upcoming/completed sessions), recent admin activity, assignments by status, largest active groups, newest users. Each card links to its management page. |
| Users | List all accounts with search (name/email), role and status filters, pagination. View details, edit profile (name, email, phone, language, role-specific profile), change role, activate/deactivate. Create trainer or student accounts. |
| Trainers | List with specialization, experience, group and student counts. Detail shows profile, statistics (groups, primary students, students in groups, upcoming sessions, assignments) and the groups the trainer runs. Create and edit trainers. |
| Students | List with level, rating, primary trainer, group count and XP; filter by level, status, trainer and group. Detail shows profile, progress (XP, streaks, puzzles solved, games), groups and assignments with the latest submission. Create and edit students. |
| Groups | List (search by group or trainer name, trainer and status filters). Create with a trainer and optional initial students; edit name, description and active flag; change the trainer; add students in a batch; remove students. |
| Puzzles | Browse every puzzle in any status (search, status, category, theme, type, source, rating range, "missing data only"). Detail shows the board, solution, metadata, usage. Each record is checked for problems. Archive or publish any puzzle. |
| Reports | Overview (attendance rate, puzzle attempts and solve rate, games by status/type/result, XP, badges, top students), assignment overview, session overview with attendance, and the paginated admin activity log. |

### Problem detection for puzzles

`issues` lists, per puzzle:

- an invalid FEN, an illegal position, an empty solution, or an illegal or
  malformed move (checked with python-chess through
  `chess_validation.validate_puzzle_solution`);
- no category, no themes, no rating.

The **missing data only** filter (`incomplete_only=true`) selects puzzles
that SQL can identify across the whole table: no category, no rating, an
empty solution, or no themes. Chess legality is checked for each listed row,
not used as a table-wide filter, because that would require loading every
puzzle.

## 2. Role permissions and security rules

All rules are enforced in the backend; the UI only mirrors them.

- Every `/admin/*` route requires the `admin` role through `require_admin`
  (declared on the router). No token or an invalid token → `401`; trainers
  and students → `403`; deactivated admins → `401`.
- **No secrets in responses.** Response schemas list fields explicitly;
  password hashes, refresh tokens and reset/verification tokens are never
  returned. Audit-log details contain field names and roles, never values of
  passwords or tokens.
- **No accidental privilege escalation.**
  - Admin accounts cannot be created directly (`POST /admin/users` accepts
    `trainer` or `student` only). Admin rights are granted only through the
    explicit role endpoint, which is audited.
  - Profile updates reject unknown fields (`extra="forbid"`), so sending
    `role`, `is_active` or `password_hash` to `PATCH /admin/users/{id}`
    returns `422` and changes nothing.
  - Public registration (`/auth/register`) still always creates students.
- **Self-protection.** An admin cannot change their own role or status
  (`409`), so they cannot lock themselves out.
- **Last-admin protection.** Demoting or deactivating an active admin fails
  with `409` if no other active admin would remain. The check locks the
  active admin rows (`SELECT … FOR UPDATE`), so two concurrent requests
  cannot remove the last two admins.
- **Deactivation** revokes all of the user's refresh tokens; their access
  tokens stop working at once because `get_current_user` rejects inactive
  users.
- **Role changes keep data consistent.** Profiles are kept when a user
  leaves a role (history such as sessions and assignments stays valid).
  A trainer who still runs groups or is the primary trainer of students must
  hand them over first (`409`); a student who is in groups must leave them
  first (`409`). Becoming a student requires a `trainer_user_id` when no
  student profile exists (`422`).
- **Email changes** are checked case-insensitively for uniqueness (`409`)
  and mark the address as unverified.
- Every mutation writes an `audit_logs` row (actor, action, entity, IP).

## 3. API reference

All IDs are UUIDs. **Trainer and student IDs are user IDs** (`users.id`),
never profile IDs. List endpoints accept `page` (≥ 1, default 1) and
`page_size` (1–100, default 20) and return:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0 }
```

Errors use FastAPI's shape: `{"detail": "..."}` for `404`/`409`/`422`
business errors, and a list of field errors for request validation `422`s.

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/admin/dashboard` | Dashboard statistics | |
| GET | `/admin/activity` | Audit log | `entity_type`, `action` |
| GET | `/admin/reports/overview` | Platform report | |
| GET | `/admin/users` | List users | `search`, `role`, `is_active` |
| POST | `/admin/users` | Create trainer/student | `201`; `role` + matching profile |
| GET | `/admin/users/{user_id}` | User detail | |
| PATCH | `/admin/users/{user_id}` | Update profile | partial; unknown fields → `422` |
| PATCH | `/admin/users/{user_id}/role` | Change role | `{role, trainer_user_id?}` |
| PATCH | `/admin/users/{user_id}/status` | Activate/deactivate | `{is_active}` |
| GET | `/admin/trainers` | List trainers | `search`, `is_active` |
| POST | `/admin/trainers` | Create trainer | `201` |
| GET | `/admin/trainers/{trainer_id}` | Trainer detail | `404` if not a trainer |
| GET | `/admin/students` | List students | `search`, `is_active`, `level`, `trainer_id`, `group_id`, `exclude_group_id` |
| POST | `/admin/students` | Create student | `201`; `profile.trainer_user_id` required |
| GET | `/admin/students/{student_id}` | Student detail | `404` if not a student |
| GET | `/admin/groups` | List groups | `search`, `is_active`, `trainer_id` |
| POST | `/admin/groups` | Create group | `201`; optional `student_user_ids` |
| GET | `/admin/groups/{group_id}` | Group detail and members | |
| PATCH | `/admin/groups/{group_id}` | Edit name/description/active | |
| PUT | `/admin/groups/{group_id}/trainer` | Assign (replace) trainer | `{trainer_user_id}` |
| POST | `/admin/groups/{group_id}/students` | Add students | `{student_user_ids: [...]}`, all-or-nothing |
| DELETE | `/admin/groups/{group_id}/students/{student_id}` | Remove student | `204` |
| GET | `/admin/puzzles` | List puzzles | `search`, `status`, `category_id`, `theme_id`, `type`, `source`, `min_rating`, `max_rating`, `incomplete_only` |
| GET | `/admin/puzzles/filters` | Filter options | categories, themes, types, sources, statuses |
| GET | `/admin/puzzles/{puzzle_id}` | Puzzle detail and usage | |
| POST | `/admin/puzzles/{puzzle_id}/archive` | Archive | from `draft`/`published` |
| POST | `/admin/puzzles/{puzzle_id}/publish` | Publish | from `draft`/`archived`; position re-validated |
| GET | `/admin/assignments` | Assignment overview | `search`, `status`, `trainer_id`, `group_id` |
| GET | `/admin/sessions` | Session overview with attendance | `status`, `timeframe=upcoming\|past`, `trainer_id`, `group_id` |

### Status codes

| Code | When |
|---|---|
| `200` / `201` / `204` | Success (`201` on create, `204` on membership removal) |
| `401` | Missing, invalid or expired token; inactive account |
| `403` | Authenticated but not an admin |
| `404` | Path resource not found (user, trainer, student, group, puzzle, membership) |
| `409` | Conflict: duplicate email, duplicate group name for the same trainer, duplicate membership, last-admin or self-change protection, role change blocked by groups/students, invalid puzzle transition |
| `422` | Invalid input, or a body reference that is missing or unsuitable (unknown trainer/student IDs, inactive trainer, non-student added to a group, student without a profile, puzzle that fails validation on publish) |

### Examples

Create a student:

```http
POST /admin/students
Authorization: Bearer <admin access token>
Content-Type: application/json

{
  "email": "maya@example.com",
  "password": "Initial-pass-1",
  "full_name": "Maya Rao",
  "phone": "+91 98450 00000",
  "profile": {
    "trainer_user_id": "9b5435b9-1f33-451a-b004-302178d971c9",
    "level": "beginner",
    "chess_rating": 800
  }
}
```

```json
201 Created
{
  "id": "4d0c…",
  "email": "maya@example.com",
  "full_name": "Maya Rao",
  "role": "student",
  "phone": "+91 98450 00000",
  "language": "en",
  "is_active": true,
  "is_verified": false,
  "last_login_at": null,
  "created_at": "2026-11-02T14:05:11Z",
  "updated_at": "2026-11-02T14:05:11Z",
  "trainer_profile": null,
  "student_profile": {
    "id": "a1f3…",
    "date_of_birth": null,
    "chess_rating": 800,
    "level": "beginner",
    "notes": null,
    "trainer": { "id": "9b54…", "full_name": "Demo Trainer", "email": "trainer@chessacademy.local" }
  },
  "groups": [],
  "trainer_stats": null,
  "student_progress": null,
  "assignments": []
}
```

Add students to a group (all-or-nothing):

```http
POST /admin/groups/{group_id}/students
{ "student_user_ids": ["4d0c…", "77e1…"] }
```

```json
409 Conflict
{ "detail": "Already members of this group: Maya Rao." }
```

Change a role:

```http
PATCH /admin/users/{user_id}/role
{ "role": "student", "trainer_user_id": "9b54…" }
```

Deactivate an account:

```http
PATCH /admin/users/{user_id}/status
{ "is_active": false }
```

## 4. Database changes

**None.** M4 adds no tables, columns or migrations; it uses the M2 schema
and the M5 migration `a5c1e7d2b934` (puzzle `status`). Alembic head remains
`a5c1e7d2b934`.

How the existing schema shapes the module:

- `users.is_active` provides account status.
- `groups.trainer_id` is a single, non-null trainer. A group therefore has
  exactly **one** trainer: "assign trainer" replaces it, and a trainer cannot
  be removed without naming a replacement. Supporting several trainers per
  group would need a new `group_trainers` table and a migration; that was not
  added without approval.
- `student_profiles.trainer_id` is non-null, so every student profile has a
  primary trainer. Self-registered students have no profile until an admin
  assigns a trainer (through the edit dialog), and they cannot join groups
  until then.
- `audit_logs` (from M2) records admin actions and powers the activity feed.

## 5. Frontend pages

| Route | Page |
|---|---|
| `#/admin/dashboard` (alias `#/admin`) | Dashboard |
| `#/admin/users`, `#/admin/users/:userId` | User management and details |
| `#/admin/trainers`, `#/admin/trainers/:userId` | Trainer management and details |
| `#/admin/students`, `#/admin/students/:userId` | Student management and details |
| `#/admin/groups`, `#/admin/groups/:groupId` | Group management and membership |
| `#/admin/puzzles`, `#/admin/puzzles/:puzzleId` | Puzzle overview and details |
| `#/admin/reports?tab=overview\|assignments\|sessions\|activity` | Reports |

Shared admin components in `src/features/admin/`: `AdminPage` (scoped
styles + toasts), `FormDialog` (native `<dialog>` form), `UserListPage`,
`AccountDialog` / `EditUserDialog` / `RoleDialog`, `GroupDialog` /
`AssignTrainerDialog` / `AddStudentsDialog`, `TrainerSelect`,
`ActivityList`, plus `api.js`, `hooks.js` (`useSubmit`), `validation.js`
and `utils.js`. Destructive actions (deactivate, remove from group,
archive) use the Trainer kit's `ConfirmDialog`. Forms validate on the client
with the same rules as the API, and show API field errors inline.

## 6. Local testing

```bash
docker compose up -d                    # db, redis, backend
docker compose exec backend alembic upgrade head
CHESS_SEED_PASSWORD=... docker compose exec -e CHESS_SEED_PASSWORD backend python scripts/seed.py

# Backend tests (admin only, then everything)
docker compose exec backend pytest tests/test_admin.py -q
docker compose exec backend pytest -q

# Frontend
cd frontend
npm run lint
npm run format:check
npm run build
npm run dev                             # http://localhost:5173
```

Sign in as the seeded admin (`admin@chessacademy.local`, password from
`CHESS_SEED_PASSWORD`) to open the admin portal.

Admin tests use the transactional `tdb` fixture from
`tests/trainer_fixtures.py`: each test runs in one outer transaction that is
rolled back, so nothing is written to the development database. Assertions
compare before/after values or filter by a per-test marker, so they pass
with or without seed data.

## 7. Known limitations

- One trainer per group (see Database changes).
- The trainer picker lists the first 100 active trainers by name.
- Student details list the 50 most recent assignments.
- Admin-created accounts get an initial password chosen by the admin; no
  invitation email is sent because email delivery is not configured yet
  (`email_service` only logs).
- Admin pages import the Trainer module's component kit; moving that kit to
  `src/components/` would make the dependency explicit.
- There are no frontend unit tests: the project has no frontend test runner.
