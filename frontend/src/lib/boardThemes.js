// Board colour themes and piece sets offered in account settings. The
// backend validates the same names (app/services/account_service.py).

export const BOARD_THEMES = {
  // Follows the app palette (and its dark mode) through CSS tokens.
  wood: { label: 'Wood', light: 'var(--color-board-light)', dark: 'var(--color-board-dark)' },
  green: { label: 'Green', light: '#eeeed2', dark: '#769656' },
  blue: { label: 'Blue', light: '#dee3e6', dark: '#8ca2ad' },
  slate: { label: 'Slate', light: '#e3e1dc', dark: '#8b8a86' },
};

export const PIECE_SETS = {
  classic: 'Classic',
  glyph: 'Glyph',
};

export const DEFAULT_BOARD_PREFS = { theme: 'wood', pieces: 'classic', show_coordinates: true };

export function boardColors(theme) {
  return BOARD_THEMES[theme] ?? BOARD_THEMES.wood;
}

const GLYPHS = { K: '♚', Q: '♛', R: '♜', B: '♝', N: '♞', P: '♟' };

/** react-chessboard piece codes ("wK", "bP", …) mapped to glyph data. */
export function glyphPieceList() {
  return ['w', 'b'].flatMap((color) =>
    Object.entries(GLYPHS).map(([type, glyph]) => ({ code: `${color}${type}`, color, glyph })),
  );
}
