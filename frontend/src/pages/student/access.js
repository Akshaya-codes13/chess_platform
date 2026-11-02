// State for the student portal gate. A self-registered student has no
// student profile until an administrator assigns a trainer; GET
// /student/access reports that as "awaiting_trainer". Kept free of React and
// browser APIs so it runs under `node --test`.

// phase: 'checking' | 'waiting' | 'ready' | 'error'
export const initialAccess = {
  phase: 'checking',
  checking: true,
  trainer: null,
  checkedAt: null,
  error: null,
  justAssigned: false,
};

export function accessReducer(state, action) {
  switch (action.type) {
    case 'check':
      return { ...state, checking: true, error: null };

    case 'loaded': {
      // Anything but an explicit "ready" keeps the student on the waiting
      // screen, so a half-set-up account never sees a broken dashboard.
      const ready = action.body?.status === 'ready';
      return {
        ...state,
        phase: ready ? 'ready' : 'waiting',
        checking: false,
        trainer: ready ? (action.body.trainer ?? null) : null,
        checkedAt: action.at,
        error: null,
        justAssigned: ready && state.phase === 'waiting',
      };
    }

    case 'failed':
      return {
        ...state,
        // A failed re-check keeps the waiting screen and shows the error there.
        phase: state.phase === 'waiting' ? 'waiting' : 'error',
        checking: false,
        error: action.message || 'Could not reach the academy server.',
      };

    default:
      return state;
  }
}
