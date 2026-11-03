"""Server-side puzzle validation with python-chess.

Stored solutions (see ``scripts/seed.py``) are space-separated UCI moves. The
first move is the student's, played from the stored FEN by the side to move,
and every second move after it is the opponent's forced reply:

    "d2d8 c7d8 d1d8"  ->  student d2d8, opponent c7d8, student d1d8

Students submit only their own moves; the opponent replies are taken from the
stored line. Nothing the client says about correctness is trusted.
"""

from dataclasses import dataclass, field

import chess

STATUS_IN_PROGRESS = "in_progress"
STATUS_SOLVED = "solved"
STATUS_FAILED = "failed"


class InvalidPuzzleError(ValueError):
    """The stored FEN or solution line cannot be played."""


class IllegalMoveError(ValueError):
    """A submitted move is malformed or illegal in its position."""


@dataclass
class PlayedMove:
    uci: str
    san: str
    fen: str
    by: str  # "student" or "opponent"


@dataclass
class LineResult:
    status: str
    board: chess.Board
    played: list[PlayedMove] = field(default_factory=list)


def load_puzzle(fen: str, solution: str) -> tuple[chess.Board, list[chess.Move]]:
    """Return the start position and the parsed solution line.

    Raises ``InvalidPuzzleError`` unless every move of the line is legal.
    """
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise InvalidPuzzleError("Puzzle position is not a valid FEN.") from exc

    if not board.is_valid():
        raise InvalidPuzzleError("Puzzle position is not a legal chess position.")

    tokens = (solution or "").split()

    if not tokens:
        raise InvalidPuzzleError("Puzzle has no solution line.")

    line = []
    replay = board.copy()

    for uci in tokens:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise InvalidPuzzleError(f"Solution contains invalid move {uci}.") from exc

        if move not in replay.legal_moves:
            raise InvalidPuzzleError(f"Solution move {uci} is illegal.")

        replay.push(move)
        line.append(move)

    return board, line


def student_moves_required(line: list[chess.Move]) -> int:
    return (len(line) + 1) // 2


def legal_moves(board: chess.Board) -> list[str]:
    return sorted(move.uci() for move in board.legal_moves)


def position_state(board: chess.Board) -> dict:
    """Describe a position for the client, including every legal move."""
    return {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "legal_moves": legal_moves(board),
        "is_check": board.is_check(),
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
    }


def solution_san(fen: str, solution: str) -> list[str]:
    board, line = load_puzzle(fen, solution)
    sans = []

    for move in line:
        sans.append(board.san(move))
        board.push(move)

    return sans


def _push(board: chess.Board, move: chess.Move, by: str) -> PlayedMove:
    san = board.san(move)
    board.push(move)
    return PlayedMove(uci=move.uci(), san=san, fen=board.fen(), by=by)


def check_line(fen: str, solution: str, student_moves: list[str]) -> LineResult:
    """Replay the student's moves against the stored solution.

    * Every submitted move must be legal, or ``IllegalMoveError`` is raised.
    * The first deviation from the line fails the attempt, except that any
      move delivering checkmate solves it (alternative mates are accepted).
    * A correct prefix that is shorter than the line is ``in_progress``; the
      opponent's reply to the last move is included in ``played``.
    """
    board, line = load_puzzle(fen, solution)
    required = student_moves_required(line)

    if not student_moves:
        raise IllegalMoveError("Submit at least one move.")

    if len(student_moves) > required:
        raise IllegalMoveError(
            f"This puzzle needs at most {required} move(s) from you."
        )

    played: list[PlayedMove] = []

    for index, uci in enumerate(student_moves):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalMoveError(f"{uci!r} is not a valid UCI move.") from exc

        if move not in board.legal_moves:
            raise IllegalMoveError(f"{uci} is not a legal move in this position.")

        expected = line[2 * index]
        played.append(_push(board, move, "student"))

        if board.is_checkmate():
            return LineResult(STATUS_SOLVED, board, played)

        if move != expected:
            return LineResult(STATUS_FAILED, board, played)

        reply_index = 2 * index + 1

        if reply_index < len(line):
            played.append(_push(board, line[reply_index], "opponent"))

    if len(student_moves) == required:
        return LineResult(STATUS_SOLVED, board, played)

    return LineResult(STATUS_IN_PROGRESS, board, played)


def hint(fen: str, solution: str, student_moves: list[str], level: int) -> dict:
    """Return a hint for the student's next move after a correct prefix.

    Level 1 names the piece and the square it moves from; level 2 also gives
    the full move. ``student_moves`` must be a correct, unfinished prefix.
    """
    board, line = load_puzzle(fen, solution)

    if student_moves:
        result = check_line(fen, solution, student_moves)

        if result.status != STATUS_IN_PROGRESS:
            raise IllegalMoveError("This attempt is already finished; restart for a hint.")

        board = result.board

    move = line[2 * len(student_moves)]
    piece = board.piece_at(move.from_square)
    payload = {
        "level": level,
        "from_square": chess.square_name(move.from_square),
        "piece": chess.piece_name(piece.piece_type) if piece else None,
        "move": None,
        "san": None,
    }

    if level >= 2:
        payload["move"] = move.uci()
        payload["san"] = board.san(move)

    return payload
