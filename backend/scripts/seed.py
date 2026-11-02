import os
import sys
import chess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running this script from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, or_, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    User,
    TrainerProfile,
    StudentProfile,
    Group,
    GroupMember,
    PuzzleCategory,
    PuzzleTheme,
    Puzzle,
    PuzzleThemeMapping,
    PuzzleAttempt,
    Assignment,
    AssignmentRecipient,
    AssignmentPuzzle,
    ClassSession,
    SessionAttendance,
    Game,
    BoardPosition,
    StudentProgress,
    XPEvent,
    Badge,
    StudentBadge,
    DailyActivity,
)


def validate_puzzle_solution(fen, solution):
    """Validate a puzzle FEN and its complete UCI solution."""
    try:
        board = chess.Board(fen)

        if not board.is_valid():
            raise ValueError("Invalid chess position.")

        moves = solution.split()

        if not moves:
            raise ValueError("Puzzle solution cannot be empty.")

        for uci in moves:
            try:
                move = chess.Move.from_uci(uci)
            except ValueError as exc:
                raise ValueError(f"Invalid UCI move: {uci}") from exc

            if move not in board.legal_moves:
                raise ValueError(
                    f"Illegal move {uci} in position: {board.fen()}"
                )

            board.push(move)

        return board

    except ValueError:
        raise

SEED_USERS = [
    {
        "email": "admin@chessacademy.local",
        "full_name": "Academy Admin",
        "role": "admin",
    },
    {
        "email": "trainer@chessacademy.local",
        "full_name": "Demo Trainer",
        "role": "trainer",
    },
    {
        "email": "student1@chessacademy.local",
        "full_name": "Demo Student One",
        "role": "student",
    },
    {
        "email": "student2@chessacademy.local",
        "full_name": "Demo Student Two",
        "role": "student",
    },
]


SAMPLE_PUZZLES = [
    {
        "lichess_id": "demo-mate-in-one-001",
        "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1",
        "solution": "g6g7",
        "rating": 800,
        "rating_deviation": 50,
        "popularity": 90,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "beginner",
        "category": "beginner",
        "themes": ["checkmate"],
        "explanation": (
            "Find the queen move that delivers checkmate in one move."
        ),
    },
    {
        "lichess_id": "demo-fork-001",
        "fen": "2q1k3/8/8/1N6/8/8/8/K7 w - - 0 1",
        "solution": "b5d6",
        "rating": 900,
        "rating_deviation": 50,
        "popularity": 90,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "beginner",
        "category": "beginner",
        "themes": ["fork"],
        "explanation": (
            "The knight moves to d6 with check, "
            "simultaneously attacking the queen on c8."
        ),
    },
    {
        "lichess_id": "demo-pin-001",
        "fen": "6k1/p5pp/8/3q4/8/1P6/P4PPP/5BK1 w - - 0 1",
        "solution": "f1c4 d5c4 b3c4",
        "rating": 950,
        "rating_deviation": 50,
        "popularity": 90,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "beginner",
        "category": "beginner",
        "themes": ["pin"],
        "explanation": (
            "Bc4 pins the queen on d5 to the king on g8. "
            "The queen cannot escape, so Black loses it for the bishop."
        ),
    },
    {
        "lichess_id": "demo-skewer-001",
        "fen": "8/p5pp/3k3q/8/8/8/5PPP/R5K1 w - - 0 1",
        "solution": "a1a6 d6e5 a6h6",
        "rating": 1000,
        "rating_deviation": 50,
        "popularity": 90,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "beginner",
        "category": "beginner",
        "themes": ["skewer"],
        "explanation": (
            "Ra6+ checks the king along the sixth rank. Once the king "
            "steps off the rank, the rook captures the queen on h6."
        ),
    },
    {
        "lichess_id": "demo-discovered-attack-001",
        "fen": "4k3/pq4pp/8/8/4N3/8/5PPP/4R1K1 w - - 0 1",
        "solution": "e4d6 e8f8 d6b7",
        "rating": 1300,
        "rating_deviation": 60,
        "popularity": 85,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "intermediate",
        "category": "intermediate",
        "themes": ["discovered-attack"],
        "explanation": (
            "Nd6+ uncovers the rook's check on the e-file while the knight "
            "also gives check. The king must move, and Nxb7 wins the queen."
        ),
    },
    {
        "lichess_id": "demo-back-rank-mate-001",
        "fen": "3r2k1/ppq2ppp/8/8/8/8/PP1R1PPP/3Q2K1 w - - 0 1",
        "solution": "d2d8 c7d8 d1d8",
        "rating": 1250,
        "rating_deviation": 60,
        "popularity": 85,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "intermediate",
        "category": "intermediate",
        "themes": ["checkmate"],
        "explanation": (
            "Rxd8+ forces Qxd8, and Qxd8# mates on the back rank because "
            "the king is boxed in by its own pawns."
        ),
    },
    {
        "lichess_id": "demo-royal-fork-001",
        "fen": "3qk2r/ppp3pp/8/4N3/8/8/PP3PPP/3Q2K1 w - - 0 1",
        "solution": "d1d8 e8d8 e5f7 d8e7 f7h8",
        "rating": 1350,
        "rating_deviation": 60,
        "popularity": 85,
        "source": "manual",
        "type": "puzzle",
        "difficulty": "intermediate",
        "category": "intermediate",
        "themes": ["fork"],
        "explanation": (
            "Qxd8+ Kxd8 trades queens and pulls the king to d8. "
            "Nf7+ then forks the king and the rook on h8."
        ),
    },
]


# Fixed timestamps keep the demo data deterministic, so the seed functions
# can look records up by their natural keys and stay idempotent.
DEMO_GROUP_NAME = "Beginner Chess Group"

DEMO_STUDENT_EMAILS = [
    "student1@chessacademy.local",
    "student2@chessacademy.local",
]

DEMO_ASSIGNMENT = {
    "title": "Beginner Tactics Practice",
    "description": (
        "Solve the beginner tactics set: checkmate, fork, pin and skewer."
    ),
    "assignment_type": "group",
    "status": "published",
    "published_at": datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc),
    "due_date": datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc),
    "puzzles": [
        "demo-mate-in-one-001",
        "demo-fork-001",
        "demo-pin-001",
        "demo-skewer-001",
    ],
}

DEMO_SESSION = {
    "title": "Beginner Tactics Class: Pins and Forks",
    "description": "Group class covering pins, forks and basic mates.",
    "session_type": "group",
    "status": "completed",
    "start_time": datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc),
    "end_time": datetime(2026, 10, 28, 16, 0, tzinfo=timezone.utc),
    "attendance": {
        "student1@chessacademy.local": ("present", None),
        "student2@chessacademy.local": ("late", "Joined 10 minutes late."),
    },
}

DEMO_GAME = {
    "white": "student1@chessacademy.local",
    "black": "student2@chessacademy.local",
    "game_type": "free",
    "status": "completed",
    "result": "white_win",
    "initial_fen": chess.STARTING_FEN,
    "moves": ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"],
    "time_control_seconds": 600,
    "started_at": datetime(2026, 10, 28, 16, 15, tzinfo=timezone.utc),
    "ended_at": datetime(2026, 10, 28, 16, 25, tzinfo=timezone.utc),
    # Snapshot move_number is the number of half-moves played from
    # initial_fen, so each FEN can be rebuilt from moves[:move_number].
    "snapshots": {
        0: "Starting position",
        2: "After 1...e5",
        5: "After 3.Qh5, threatening Qxf7#",
        7: "Final position after 4.Qxf7#",
    },
}

GAME_RESULTS = {
    "white_win": chess.WHITE,
    "black_win": chess.BLACK,
    "draw": None,
}

PUZZLE_SOLVED_XP = 10

GAME_RESULT_XP = {"win": 15, "draw": 10, "loss": 5}

DEMO_BADGES = [
    {
        "code": "first-puzzle-solved",
        "name": "First Puzzle Solved",
        "description": "Solve your first puzzle.",
        "xp_reward": 10,
    },
    {
        "code": "three-puzzles-solved",
        "name": "Tactics Trio",
        "description": "Solve three puzzles.",
        "xp_reward": 20,
    },
    {
        "code": "first-game-played",
        "name": "First Game",
        "description": "Complete your first game.",
        "xp_reward": 10,
    },
]

# Badge code -> (StudentProgress counter, threshold) required to earn it.
BADGE_REQUIREMENTS = {
    "first-puzzle-solved": ("puzzles_solved", 1),
    "three-puzzles-solved": ("puzzles_solved", 3),
    "first-game-played": ("games_played", 1),
}

# Student email -> (puzzle lichess_id, is_solved, seconds, attempted_at).
DEMO_PUZZLE_ATTEMPTS = {
    "student1@chessacademy.local": [
        ("demo-mate-in-one-001", True, 20,
         datetime(2026, 10, 28, 16, 30, tzinfo=timezone.utc)),
        ("demo-fork-001", True, 45,
         datetime(2026, 10, 28, 16, 35, tzinfo=timezone.utc)),
        ("demo-pin-001", False, 90,
         datetime(2026, 10, 28, 16, 40, tzinfo=timezone.utc)),
        ("demo-pin-001", True, 60,
         datetime(2026, 10, 29, 17, 0, tzinfo=timezone.utc)),
        ("demo-skewer-001", True, 50,
         datetime(2026, 10, 29, 17, 5, tzinfo=timezone.utc)),
        ("demo-discovered-attack-001", False, 150,
         datetime(2026, 10, 29, 17, 10, tzinfo=timezone.utc)),
    ],
    "student2@chessacademy.local": [
        ("demo-mate-in-one-001", True, 25,
         datetime(2026, 10, 28, 16, 30, tzinfo=timezone.utc)),
        ("demo-fork-001", False, 120,
         datetime(2026, 10, 28, 16, 36, tzinfo=timezone.utc)),
        ("demo-fork-001", True, 70,
         datetime(2026, 10, 29, 17, 10, tzinfo=timezone.utc)),
    ],
}


def get_or_create_user(db, user_data, password_hash):
    user = db.scalar(
        select(User).where(
            func.lower(User.email) == user_data["email"].lower()
        )
    )

    if user:
        if user.role != user_data["role"]:
            raise ValueError(
                f"{user.email} already exists with a different role."
            )

        print(f"Existing user preserved: {user.email}")
        return user

    user = User(
        **user_data,
        password_hash=password_hash,
        is_active=True,
        is_verified=True,
    )

    db.add(user)
    db.flush()

    print(f"Created user: {user.email}")
    return user



def seed_accounts(db, password_hash):
    users = {}

    for data in SEED_USERS:
        users[data["role"]] = get_or_create_user(
            db, data, password_hash
        )

    trainer_user = users["trainer"]

    trainer_profile = db.scalar(
        select(TrainerProfile).where(
            TrainerProfile.user_id == trainer_user.id
        )
    )

    if not trainer_profile:
        trainer_profile = TrainerProfile(
            user_id=trainer_user.id,
            bio="Development trainer account.",
            specialization="Chess fundamentals",
            experience_years=3,
        )
        db.add(trainer_profile)
        db.flush()
        print("Created trainer profile.")
    else:
        print("Existing trainer profile preserved.")

    student_emails = [
        "student1@chessacademy.local",
        "student2@chessacademy.local",
    ]

    for email in student_emails:
        student_user = db.scalar(
            select(User).where(
                func.lower(User.email) == email.lower()
            )
        )

        if not student_user:
            raise ValueError(f"Student account not found: {email}")

        profile = db.scalar(
            select(StudentProfile).where(
                StudentProfile.user_id == student_user.id
            )
        )

        if not profile:
            db.add(
                StudentProfile(
                    user_id=student_user.id,
                    trainer_id=trainer_profile.id,
                    chess_rating=800,
                    level="beginner",
                )
            )
            print(f"Created student profile: {email}")
        else:
            print(f"Existing student profile preserved: {email}")

def seed_group(db):
    trainer_profile = db.scalar(
        select(TrainerProfile).join(User).where(
            User.email == "trainer@chessacademy.local"
        )
    )

    if not trainer_profile:
        raise ValueError("Demo trainer profile not found.")

    group = db.scalar(
        select(Group).where(
            Group.trainer_id == trainer_profile.id,
            Group.name == "Beginner Chess Group",
        )
    )

    if not group:
        group = Group(
            trainer_id=trainer_profile.id,
            name="Beginner Chess Group",
            description="Demo group for beginner chess students.",
            is_active=True,
        )
        db.add(group)
        db.flush()
        print("Created Beginner Chess Group.")
    else:
        print("Existing Beginner Chess Group preserved.")

    student_emails = [
        "student1@chessacademy.local",
        "student2@chessacademy.local",
    ]

    for email in student_emails:
        student_profile = db.scalar(
            select(StudentProfile).join(User).where(
                User.email == email
            )
        )

        if not student_profile:
            raise ValueError(f"Student profile not found: {email}")

        membership = db.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.student_id == student_profile.id,
            )
        )

        if not membership:
            db.add(
                GroupMember(
                    group_id=group.id,
                    student_id=student_profile.id,
                )
            )
            print(f"Added {email} to Beginner Chess Group.")
        else:
            print(f"Existing membership preserved: {email}")

def seed_puzzle_taxonomy(db):
    categories = [
        {
            "name": "Beginner",
            "slug": "beginner",
            "description": "Fundamental chess puzzles for beginners.",
        },
        {
            "name": "Intermediate",
            "slug": "intermediate",
            "description": "Puzzles requiring tactical calculation.",
        },
        {
            "name": "Advanced",
            "slug": "advanced",
            "description": "Challenging tactical and strategic puzzles.",
        },
    ]

    themes = [
        {
            "name": "Fork",
            "slug": "fork",
            "description": "One piece attacks two or more enemy pieces.",
        },
        {
            "name": "Pin",
            "slug": "pin",
            "description": "A piece cannot move without exposing a more valuable piece.",
        },
        {
            "name": "Skewer",
            "slug": "skewer",
            "description": "An attacked valuable piece moves, exposing another piece behind it.",
        },
        {
            "name": "Discovered Attack",
            "slug": "discovered-attack",
            "description": "Moving one piece reveals an attack from another piece.",
        },
        {
            "name": "Checkmate",
            "slug": "checkmate",
            "description": "Puzzles focused on delivering checkmate.",
        },
    ]

    for data in categories:
        existing = db.scalar(
            select(PuzzleCategory).where(
                PuzzleCategory.slug == data["slug"]
            )
        )
        if existing is None:
            db.add(PuzzleCategory(**data))
            print(f"Created puzzle category: {data['name']}")
        else:
            print(f"Existing puzzle category preserved: {data['name']}")

    for data in themes:
        existing = db.scalar(
            select(PuzzleTheme).where(
                PuzzleTheme.slug == data["slug"]
            )
        )
        if existing is None:
            db.add(PuzzleTheme(**data))
            print(f"Created puzzle theme: {data['name']}")
        else:
            print(f"Existing puzzle theme preserved: {data['name']}")

    db.flush()


def seed_sample_puzzles(db):
    for data in SAMPLE_PUZZLES:
        validate_puzzle_solution(data["fen"], data["solution"])

        category = db.scalar(
            select(PuzzleCategory).where(
                PuzzleCategory.slug == data["category"]
            )
        )

        if category is None:
            raise ValueError(
                f"Puzzle category not found: {data['category']}"
            )

        puzzle = db.scalar(
            select(Puzzle).where(
                Puzzle.lichess_id == data["lichess_id"]
            )
        )

        if puzzle is None:
            puzzle = Puzzle(
                lichess_id=data["lichess_id"],
                fen=data["fen"],
                solution=data["solution"],
                rating=data["rating"],
                rating_deviation=data["rating_deviation"],
                popularity=data["popularity"],
                source=data["source"],
                type=data["type"],
                difficulty=data["difficulty"],
                explanation=data["explanation"],
                category_id=category.id,
            )
            db.add(puzzle)
            db.flush()
            print(f"Created puzzle: {data['lichess_id']}")
        else:
            print(f"Existing puzzle preserved: {data['lichess_id']}")

        for theme_slug in data["themes"]:
            theme = db.scalar(
                select(PuzzleTheme).where(
                    PuzzleTheme.slug == theme_slug
                )
            )

            if theme is None:
                raise ValueError(
                    f"Puzzle theme not found: {theme_slug}"
                )

            mapping = db.scalar(
                select(PuzzleThemeMapping).where(
                    PuzzleThemeMapping.puzzle_id == puzzle.id,
                    PuzzleThemeMapping.theme_id == theme.id,
                )
            )

            if mapping is None:
                db.add(
                    PuzzleThemeMapping(
                        puzzle_id=puzzle.id,
                        theme_id=theme.id,
                    )
                )
                print(
                    f"Mapped {data['lichess_id']} to theme {theme_slug}"
                )

    db.flush()


def get_demo_trainer_profile(db):
    trainer_profile = db.scalar(
        select(TrainerProfile).join(User).where(
            User.email == "trainer@chessacademy.local"
        )
    )

    if trainer_profile is None:
        raise ValueError("Demo trainer profile not found.")

    return trainer_profile


def get_demo_group(db, trainer_profile):
    group = db.scalar(
        select(Group).where(
            Group.trainer_id == trainer_profile.id,
            Group.name == DEMO_GROUP_NAME,
        )
    )

    if group is None:
        raise ValueError(f"{DEMO_GROUP_NAME} not found.")

    return group


def get_student_profile(db, email):
    student_profile = db.scalar(
        select(StudentProfile).join(User).where(User.email == email)
    )

    if student_profile is None:
        raise ValueError(f"Student profile not found: {email}")

    return student_profile


def get_puzzle(db, lichess_id):
    puzzle = db.scalar(
        select(Puzzle).where(Puzzle.lichess_id == lichess_id)
    )

    if puzzle is None:
        raise ValueError(f"Puzzle not found: {lichess_id}")

    return puzzle


def get_demo_assignment(db):
    trainer_profile = get_demo_trainer_profile(db)
    group = get_demo_group(db, trainer_profile)

    return db.scalar(
        select(Assignment).where(
            Assignment.trainer_id == trainer_profile.id,
            Assignment.group_id == group.id,
            Assignment.title == DEMO_ASSIGNMENT["title"],
        )
    )


def get_demo_game(db):
    white = db.scalar(select(User).where(User.email == DEMO_GAME["white"]))
    black = db.scalar(select(User).where(User.email == DEMO_GAME["black"]))

    if white is None or black is None:
        raise ValueError("Demo game players not found.")

    return white, black, db.scalar(
        select(Game).where(
            Game.white_id == white.id,
            Game.black_id == black.id,
            Game.started_at == DEMO_GAME["started_at"],
        )
    )


def replay_game(initial_fen, moves):
    """Replay UCI moves and return the FEN after each half-move.

    Index 0 is the initial position, index n is the position after n moves.
    """
    board = chess.Board(initial_fen)

    if not board.is_valid():
        raise ValueError("Invalid initial game position.")

    fens = [board.fen()]

    for uci in moves:
        move = chess.Move.from_uci(uci)

        if move not in board.legal_moves:
            raise ValueError(f"Illegal move {uci} in position: {board.fen()}")

        board.push(move)
        fens.append(board.fen())

    return board, fens


def seed_assignment(db):
    trainer_profile = get_demo_trainer_profile(db)
    group = get_demo_group(db, trainer_profile)

    assignment = get_demo_assignment(db)

    if assignment is None:
        assignment = Assignment(
            trainer_id=trainer_profile.id,
            group_id=group.id,
            title=DEMO_ASSIGNMENT["title"],
            description=DEMO_ASSIGNMENT["description"],
            assignment_type=DEMO_ASSIGNMENT["assignment_type"],
            status=DEMO_ASSIGNMENT["status"],
            published_at=DEMO_ASSIGNMENT["published_at"],
            due_date=DEMO_ASSIGNMENT["due_date"],
        )
        db.add(assignment)
        db.flush()
        print(f"Created assignment: {assignment.title}")
    else:
        print(f"Existing assignment preserved: {assignment.title}")

    for order, lichess_id in enumerate(DEMO_ASSIGNMENT["puzzles"], start=1):
        puzzle = get_puzzle(db, lichess_id)

        mapping = db.scalar(
            select(AssignmentPuzzle).where(
                AssignmentPuzzle.assignment_id == assignment.id,
                AssignmentPuzzle.puzzle_id == puzzle.id,
            )
        )

        if mapping is None:
            db.add(
                AssignmentPuzzle(
                    assignment_id=assignment.id,
                    puzzle_id=puzzle.id,
                    points=1,
                    display_order=order,
                )
            )
            print(f"Added {lichess_id} to assignment.")

    for email in DEMO_STUDENT_EMAILS:
        student_profile = get_student_profile(db, email)

        recipient = db.scalar(
            select(AssignmentRecipient).where(
                AssignmentRecipient.assignment_id == assignment.id,
                AssignmentRecipient.student_id == student_profile.id,
            )
        )

        if recipient is None:
            db.add(
                AssignmentRecipient(
                    assignment_id=assignment.id,
                    student_id=student_profile.id,
                )
            )
            print(f"Assigned to {email}.")
        else:
            print(f"Existing assignment recipient preserved: {email}")

    db.flush()


def seed_class_session(db):
    trainer_profile = get_demo_trainer_profile(db)
    group = get_demo_group(db, trainer_profile)

    session = db.scalar(
        select(ClassSession).where(
            ClassSession.trainer_id == trainer_profile.id,
            ClassSession.group_id == group.id,
            ClassSession.start_time == DEMO_SESSION["start_time"],
        )
    )

    if session is None:
        session = ClassSession(
            trainer_id=trainer_profile.id,
            group_id=group.id,
            title=DEMO_SESSION["title"],
            description=DEMO_SESSION["description"],
            session_type=DEMO_SESSION["session_type"],
            status=DEMO_SESSION["status"],
            start_time=DEMO_SESSION["start_time"],
            end_time=DEMO_SESSION["end_time"],
        )
        db.add(session)
        db.flush()
        print(f"Created class session: {session.title}")
    else:
        print(f"Existing class session preserved: {session.title}")

    for email, (status, remarks) in DEMO_SESSION["attendance"].items():
        student_profile = get_student_profile(db, email)

        attendance = db.scalar(
            select(SessionAttendance).where(
                SessionAttendance.session_id == session.id,
                SessionAttendance.student_id == student_profile.id,
            )
        )

        if attendance is None:
            db.add(
                SessionAttendance(
                    session_id=session.id,
                    student_id=student_profile.id,
                    status=status,
                    remarks=remarks,
                )
            )
            print(f"Recorded attendance for {email}: {status}")
        else:
            print(f"Existing attendance preserved: {email}")

    db.flush()


def seed_game(db):
    board, fens = replay_game(DEMO_GAME["initial_fen"], DEMO_GAME["moves"])

    outcome = board.outcome()

    if outcome is None or outcome.winner != GAME_RESULTS[DEMO_GAME["result"]]:
        raise ValueError("Demo game moves do not match its result.")

    white, black, game = get_demo_game(db)

    if game is None:
        game = Game(
            white_id=white.id,
            black_id=black.id,
            game_type=DEMO_GAME["game_type"],
            status=DEMO_GAME["status"],
            result=DEMO_GAME["result"],
            initial_fen=DEMO_GAME["initial_fen"],
            current_fen=fens[-1],
            moves=DEMO_GAME["moves"],
            time_control_seconds=DEMO_GAME["time_control_seconds"],
            started_at=DEMO_GAME["started_at"],
            ended_at=DEMO_GAME["ended_at"],
        )
        db.add(game)
        db.flush()
        print("Created demo game.")
    else:
        print("Existing demo game preserved.")

    for move_number, label in DEMO_GAME["snapshots"].items():
        position = db.scalar(
            select(BoardPosition).where(
                BoardPosition.game_id == game.id,
                BoardPosition.move_number == move_number,
            )
        )

        if position is None:
            db.add(
                BoardPosition(
                    game_id=game.id,
                    fen=fens[move_number],
                    move_number=move_number,
                    label=label,
                )
            )
            print(f"Saved board position: {label}")

    db.flush()


def seed_badges(db):
    for data in DEMO_BADGES:
        badge = db.scalar(select(Badge).where(Badge.code == data["code"]))

        if badge is None:
            db.add(Badge(**data))
            print(f"Created badge: {data['name']}")
        else:
            print(f"Existing badge preserved: {data['name']}")

    db.flush()


def get_or_create_xp_event(
    db, student_id, points, reason, source_type, source_id, created_at
):
    event = db.scalar(
        select(XPEvent).where(
            XPEvent.student_id == student_id,
            XPEvent.source_type == source_type,
            XPEvent.source_id == source_id,
        )
    )

    if event is None:
        event = XPEvent(
            student_id=student_id,
            points=points,
            reason=reason,
            source_type=source_type,
            source_id=source_id,
            created_at=created_at,
        )
        db.add(event)

    return event


def get_completed_games(db, user_id):
    return db.scalars(
        select(Game).where(
            Game.status == "completed",
            Game.result.in_(list(GAME_RESULTS)),
            or_(Game.white_id == user_id, Game.black_id == user_id),
        )
    ).all()


def game_outcome_for(game, user_id):
    if game.result == "draw":
        return "draw"

    winner_id = game.white_id if game.result == "white_win" else game.black_id
    return "win" if winner_id == user_id else "loss"


def activity_date(value):
    return value.astimezone(timezone.utc).date()


def calculate_streaks(dates):
    """Return (current, longest) runs of consecutive activity days.

    The current streak is the run ending on the most recent activity day.
    """
    current = longest = 0
    previous = None

    for day in sorted(dates):
        if previous is not None and day - previous == timedelta(days=1):
            current += 1
        else:
            current = 1

        longest = max(longest, current)
        previous = day

    return current, longest


def seed_student_progress(db):
    assignment = get_demo_assignment(db)
    assignment_puzzles = set(DEMO_ASSIGNMENT["puzzles"])
    badges = {
        badge.code: badge
        for badge in db.scalars(
            select(Badge).where(Badge.code.in_(list(BADGE_REQUIREMENTS)))
        )
    }

    for email, attempts in DEMO_PUZZLE_ATTEMPTS.items():
        student = get_student_profile(db, email)

        for lichess_id, is_solved, seconds, attempted_at in attempts:
            puzzle = get_puzzle(db, lichess_id)

            attempt = db.scalar(
                select(PuzzleAttempt).where(
                    PuzzleAttempt.student_id == student.id,
                    PuzzleAttempt.puzzle_id == puzzle.id,
                    PuzzleAttempt.attempted_at == attempted_at,
                )
            )

            if attempt is None:
                attempt = PuzzleAttempt(
                    student_id=student.id,
                    puzzle_id=puzzle.id,
                    assignment_id=(
                        assignment.id
                        if assignment and lichess_id in assignment_puzzles
                        else None
                    ),
                    is_solved=is_solved,
                    time_taken_seconds=seconds,
                    attempted_at=attempted_at,
                )
                db.add(attempt)
                db.flush()
                print(f"Recorded attempt for {email}: {lichess_id}")

            if attempt.is_solved:
                get_or_create_xp_event(
                    db, student.id, PUZZLE_SOLVED_XP,
                    f"Solved puzzle {lichess_id}",
                    "puzzle_attempt", attempt.id, attempt.attempted_at,
                )

        # Everything below is derived from the stored rows, so totals stay
        # consistent with the attempts, games and XP events in the database.
        solved_attempts = db.scalars(
            select(PuzzleAttempt).where(
                PuzzleAttempt.student_id == student.id,
                PuzzleAttempt.is_solved.is_(True),
            )
        ).all()
        games = get_completed_games(db, student.user_id)

        for game in games:
            outcome = game_outcome_for(game, student.user_id)
            get_or_create_xp_event(
                db, student.id, GAME_RESULT_XP[outcome],
                f"Completed a game ({outcome})",
                "game", game.id, game.ended_at,
            )

        milestones = sorted(
            [(a.attempted_at, "puzzles_solved") for a in solved_attempts]
            + [(g.ended_at, "games_played") for g in games]
        )
        counters = defaultdict(int)

        for reached_at, counter in milestones:
            counters[counter] += 1

            for code, (required_counter, threshold) in BADGE_REQUIREMENTS.items():
                if required_counter != counter or counters[counter] != threshold:
                    continue

                badge = badges.get(code)

                if badge is None:
                    raise ValueError(f"Badge not found: {code}")

                award = db.scalar(
                    select(StudentBadge).where(
                        StudentBadge.student_id == student.id,
                        StudentBadge.badge_id == badge.id,
                    )
                )

                if award is None:
                    db.add(
                        StudentBadge(
                            student_id=student.id,
                            badge_id=badge.id,
                            earned_at=reached_at,
                        )
                    )
                    print(f"Awarded badge {badge.name} to {email}")

                if badge.xp_reward:
                    get_or_create_xp_event(
                        db, student.id, badge.xp_reward,
                        f"Earned badge {badge.name}",
                        "badge", badge.id, reached_at,
                    )

        db.flush()

        all_attempts = db.scalars(
            select(PuzzleAttempt).where(PuzzleAttempt.student_id == student.id)
        ).all()
        xp_events = db.scalars(
            select(XPEvent).where(XPEvent.student_id == student.id)
        ).all()

        daily = defaultdict(lambda: defaultdict(int))

        for attempt in all_attempts:
            day = daily[activity_date(attempt.attempted_at)]
            day["puzzles_attempted"] += 1
            day["puzzles_solved"] += int(attempt.is_solved)

        for game in games:
            daily[activity_date(game.ended_at)]["games_played"] += 1

        for event in xp_events:
            daily[activity_date(event.created_at)]["xp_earned"] += event.points

        for day, totals in sorted(daily.items()):
            activity = db.scalar(
                select(DailyActivity).where(
                    DailyActivity.student_id == student.id,
                    DailyActivity.activity_date == day,
                )
            )

            if activity is None:
                db.add(
                    DailyActivity(
                        student_id=student.id,
                        activity_date=day,
                        **totals,
                    )
                )
                print(f"Recorded daily activity for {email}: {day}")

        progress = db.scalar(
            select(StudentProgress).where(
                StudentProgress.student_id == student.id
            )
        )

        if progress is None:
            current_streak, longest_streak = calculate_streaks(daily)
            db.add(
                StudentProgress(
                    student_id=student.id,
                    total_xp=sum(event.points for event in xp_events),
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                    puzzles_solved=len(solved_attempts),
                    games_played=len(games),
                )
            )
            print(f"Created student progress: {email}")
        else:
            print(f"Existing student progress preserved: {email}")

    db.flush()


def seed_all(db, password_hash):
    seed_accounts(db, password_hash)
    seed_group(db)  # <-- This is where you call it.
    seed_puzzle_taxonomy(db)
    seed_sample_puzzles(db)
    seed_badges(db)
    seed_assignment(db)
    seed_class_session(db)
    seed_game(db)
    seed_student_progress(db)


def main():
    password = os.getenv("CHESS_SEED_PASSWORD")

    if not password:
        raise RuntimeError(
            "Set CHESS_SEED_PASSWORD before running the seed script."
        )

    password_hash = hash_password(password)

    db = SessionLocal()

    try:
        seed_all(db, password_hash)

        db.commit()
        print("\nDemo data seeding completed successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

if __name__ == "__main__":
    main()