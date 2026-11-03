import chess

# Longest accepted solution line, in half-moves.
MAX_SOLUTION_PLIES = 40


def normalize_solution(solution: str) -> str:
    """Collapse whitespace and lowercase a space-separated UCI move line."""
    return " ".join(solution.lower().split())


def validate_puzzle_solution(fen, solution):
    """Validate a puzzle FEN and its complete UCI solution.

    The FEN must parse and describe a legal position, and every move must be
    legal when played in order from it. Returns the board after the last
    move; raises ``ValueError`` describing the first problem found.
    """
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ValueError(f"Invalid FEN: {exc}") from exc

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


def validate_trainer_puzzle(fen: str, solution: str) -> tuple[str, str]:
    """Validate a puzzle authored through the Trainer module.

    Applies ``validate_puzzle_solution`` and additionally rejects a finished
    starting position, a line that continues after checkmate or stalemate,
    and over-long lines. Returns the canonical FEN and normalized solution.
    """
    fen = " ".join(fen.split())
    solution = normalize_solution(solution)
    moves = solution.split()

    # python-chess fills in missing trailing fields; require a complete FEN.
    if len(fen.split()) != 6:
        raise ValueError("Invalid FEN: expected 6 space-separated fields.")

    if len(moves) > MAX_SOLUTION_PLIES:
        raise ValueError(
            f"Solution cannot be longer than {MAX_SOLUTION_PLIES} half-moves."
        )

    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ValueError(f"Invalid FEN: {exc}") from exc

    if board.is_valid() and board.is_game_over():
        raise ValueError("The starting position is already game over.")

    validate_puzzle_solution(fen, solution)

    for number, uci in enumerate(moves, start=1):
        board.push_uci(uci)

        if board.is_game_over() and number < len(moves):
            raise ValueError(
                f"The solution continues after the game ends at move {number} ({uci})."
            )

    return chess.Board(fen).fen(), solution
