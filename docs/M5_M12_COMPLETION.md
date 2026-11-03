# M5–M12 — Completion notes

This milestone set completes profiles, the chess board, sessions,
assignments, the PGN game library, gamification, reports and content. It
builds on the earlier Admin (`M4_ADMIN_MODULE.md`), Trainer
(`M5_TRAINER_MODULE.md`) and Student (`M6_STUDENT_MODULE.md`) modules.
Those documents use an older numbering; this one follows the M5–M12 plan
below.

## Checklist

Status before this work → now. "Done" items were re-verified by tests.

| # | Feature | Before | Now |
|---|---|---|---|
| M5 | Admin creates, edits, activates and deactivates trainers and students | Done | Verified |
| | Trainer-to-student assignment (`student_profiles.trainer_id`, groups) | Done | Verified |
| | Role isolation | Done | Verified, and extended to every new route |
| | Profile and account settings for every role, including admins | Partial | **Done**: `/account/settings`, Settings page |
| | Language | Partial | **Done** for all roles |
| | Notification preferences | Missing | **Done** (per category, plus email copy) |
| | Change password while signed in | Missing | **Done** (revokes other sessions) |
| M6 | Board with legal move validation | Partial (in-house board) | **Done**: react-chessboard + chess.js; puzzle moves still validated by python-chess on the server |
| | Hints | Missing | **Done** (piece first, then the move) |
| | Solved and failed states | Done | Verified |
| | Lichess puzzle import | Missing | **Done**: `scripts/import_lichess_puzzles.py`; 400 puzzles imported in dev |
| | Board theme and piece-set preferences | Missing | **Done** |
| | Attempts store moves, result, hints and timestamp | Partial (no moves) | **Done** |
| M7 | Sessions with date and time | Done | Verified |
| | Sessions for selected students | Missing | **Done** |
| | Active / Upcoming / Completed tabs | Partial | **Done** |
| | Attendance | Done | Verified, and extended to individual sessions |
| | Notifications | Missing | **Done** (scheduled, updated, cancelled) |
| | Students see their sessions | Done | Verified, invite-only for individual sessions |
| M8 | Assignments with puzzle sets and due dates | Done | Verified |
| | Positions | Partial | Positions become puzzles: board editor → "Create puzzle from position" |
| | Student submits | Partial (auto only) | **Done**: auto-submit, hand in partial work, resubmit after return |
| | Trainer reviews submissions | Missing | **Done**: attempts with moves and hints; grade or return with feedback |
| M9 | PGN upload and storage, folders, databases, breadcrumbs | Missing | **Done** |
| | Replay with move list and controls | Missing | **Done** (buttons, clickable moves, ← → Home End) |
| | Stockfish.js analysis | Missing | **Done** (lite WASM engine in a Web Worker, 3 lines) |
| | Board editor | Missing | **Done** |
| | PDF loading (pdf.js) | Missing | **Deferred**, see limitations |
| M10 | XP, badges, streaks | Done | Verified |
| | Levels | Missing | **Done** (derived from XP) |
| | XP and badges for completed assignments | Missing | **Done** (+25 XP; two new badges) |
| | Redis for streaks | Missing | **Done** (cache; the database stays the source of truth) |
| | Achievements and consistency graph | Partial | **Done** (level bar and a 16-week calendar) |
| M11 | Trainer reports | Partial | **Done** (`/trainer/reports`) |
| | Admin statistics from precomputed daily tables, built by an ARQ job | Missing | **Done** (`/admin/statistics`) |
| | Recharts | Missing | **Done** |
| M12 | Articles, blogs and photos with publishing permissions | Missing | **Done** |
| | Image storage | Missing | **Done**: storage interface with a local Docker volume |
| | Feedback (student → trainer, trainer → admins) and review | Missing | **Done** |

## Running it

```bash
docker compose up -d                       # db, redis, backend, worker
docker compose exec backend alembic upgrade head
cd frontend && npm install && npm run dev  # predev copies Stockfish to public/stockfish
```

- **Worker:** the `worker` service runs `arq app.worker.WorkerSettings`.
  - On first start it backfills the last 30 days of report rows.
  - It recomputes yesterday at 00:15 UTC and today at 5 minutes past every hour.
  - Admins can queue a recompute with **Statistics → Recalculate now**. If the queue is unreachable, today is computed inline.
- **Lichess puzzles:** download `lichess_db_puzzle.csv.zst` from <https://database.lichess.org/#puzzles> (CC0) and decompress it. Then copy the file into the backend container and run:

  ```bash
  python -m scripts.import_lichess_puzzles /tmp/lichess_puzzles.csv --limit 200 --per-difficulty 70
  ```

  The importer:
  - applies the CSV's first (opponent) move, so the stored FEN has the student to move;
  - validates every line with python-chess;
  - maps rating to difficulty and category;
  - creates missing themes.

  Re-running the same command adds nothing.

## Database (revision `6da2d4bece7b`, additive only)

| Change | Purpose |
|---|---|
| `puzzle_attempts.moves` (JSONB), `hints_used` | M6: what the student played |
| `game_databases`, `game_folders` (nested), `pgn_games` | M9: game library |
| `daily_platform_summaries`, `daily_trainer_summaries` | M11: precomputed report rows (upserted per day) |
| `media_files` | M12: uploaded images |
| `posts.published_at`, post status check | M12 |
| `feedback.audience`, `rating`, `status`, `response`, `reviewed_by`, `reviewed_at`; `to_user_id` now nullable | M12: admin-team feedback has no single recipient |
| Badges `first-assignment-completed`, `five-assignments-completed` | M10 (`ON CONFLICT DO NOTHING`) |

How the migration was handled:
- Existing rows keep their meaning.
- The downgrade refuses to run while admin-team feedback exists, instead of deleting it.
- The migration was upgrade/downgrade/upgrade tested on the dev database.

Settings live in the existing `users.settings` JSONB; only whitelisted keys are written.

## API added

| Area | Endpoints |
|---|---|
| Account (all roles) | `GET/PATCH /account/settings`, `POST /account/password` |
| Notifications | `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Puzzles | `POST /student/puzzles/{id}/hint`; attempts accept `hints_used` |
| Assignments | `POST /student/assignments/{id}/submit`; `GET /trainer/assignments/{id}/submissions/{student_id}`, `POST …/review` |
| Sessions | `POST /trainer/sessions` accepts `student_ids`; `scope=active\|completed` |
| Game library | `/games/databases` (CRUD), `/games/databases/{id}/browse`, `/folders`, `/import` (multipart file or `pgn` text), `/games/{id}` (GET, PATCH to move, DELETE) |
| Content | `/content/posts` (CRUD and `publish`/`unpublish`/`archive`), `POST /content/media`, `GET /media/{key}` |
| Feedback | `GET /feedback/recipients`, `GET/POST /feedback`, `GET /feedback/{id}`, `POST /feedback/{id}/review` |
| Reports | `GET /admin/reports/daily`, `POST /admin/reports/daily/refresh`, `GET /trainer/reports/daily` |

## Permission rules

- **Account and notifications:** a user only ever sees their own records. Another user's notification returns 404.
- **Game library:**
  - Everyone can keep private databases.
  - Only trainers and admins can share one; shared databases are read-only for others.
  - Only the owner or an admin can change a database.
  - Folders and databases must be empty before they can be deleted.
- **Posts:**
  - Only admins and trainers can create posts.
  - The author or an admin can manage a post.
  - Drafts and archived posts are visible only to their author and to admins (404 for everyone else).
  - A published post must be unpublished or archived before it can be deleted.
  - Images must be platform uploads. Only PNG, JPEG, WebP and GIF are accepted, detected from the file's bytes; SVG is rejected. The limit is 5 MB.
- **Feedback:**
  - Students write only to their primary trainer or their group trainers.
  - Trainers write to the admin team; admins don't send feedback.
  - Only the recipient can review (admins for the admin team).
- **Submissions:** only the owning trainer can review them, and only for recipients of the assignment.

## Gamification rules (additions)

- **Assignment completion:** completing an assignment gives `ASSIGNMENT_COMPLETED_XP = 25`, once per assignment. Badges then use the number of assignments the student has submitted.
- **Levels:** XP thresholds are 0, 50, 150, 300, 500, 750, 1050, 1400, 1800 and 2250; after that, each level costs 500 more (`level_for_xp`).
- **Streak cache:** streaks are cached in Redis under `streak:<student id>` with a 3-day TTL. The cache is written after each recorded attempt. A miss or a Redis failure falls back to `daily_activity`.

## Tests

- **Backend:** 44 new tests on top of the earlier suite, 311 in total:
  - `test_student_workflow.py`
  - `test_sessions_account_notifications.py`
  - `test_games_library.py`
  - `test_content_feedback.py`
  - `test_reports_summaries.py`
- **Frontend:** `node --test` unit tests for the board editor, engine output parsing and board themes (`src/lib/chess.test.js`).

## Known limitations

- **PDF (pdf.js) is deferred.** Reading PDFs needs a separate viewer and upload type; the storage interface and `media_files` can host PDFs when it is added.
- **Hint counts are self-reported.** Hints are not stored server-side per attempt in progress; the client reports `hints_used` with the finished attempt. XP is not reduced for hints, so there is no incentive to under-report.
- **Email is still not configured.** The "email" notification preference is logged by `email_service`.
- **Media URLs are public.** They are random and unguessable, and served without authentication so `<img>` works. Don't upload private material.
- **The engine is the lite, single-threaded Stockfish 19** (≈1.8 MB). It is strong, but weaker than full Stockfish.
- **Keyboard play:** react-chessboard has no keyboard navigation of its own. Every interactive board instead has a "Type a move" field (SAN or UCI).
- **Pre-existing `refresh_tokens` drift.** `alembic check` reports an index and constraint naming difference on `refresh_tokens` that predates this work. It was left untouched.
- **CI schema setup.** CI runs `pytest` without creating the schema (no migration step). This predates this work, and `.github/` was not modified.
