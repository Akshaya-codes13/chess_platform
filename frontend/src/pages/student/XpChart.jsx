import { useState } from 'react';
import { formatDate } from '../../lib/format';

const DAYS = 30;

function lastDays(daily) {
  const byDate = Object.fromEntries(daily.map((d) => [d.date, d]));
  const today = new Date();
  return Array.from({ length: DAYS }, (_, i) => {
    const day = new Date(
      Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - (DAYS - 1 - i)),
    );
    const key = day.toISOString().slice(0, 10);
    return byDate[key] ?? { date: key, puzzles_attempted: 0, puzzles_solved: 0, xp_earned: 0 };
  });
}

/** XP earned per UTC day over the last 30 days: one series, hover tooltip, table view. */
export default function XpChart({ daily }) {
  const [showTable, setShowTable] = useState(false);
  const [hover, setHover] = useState(null);
  const days = lastDays(daily);
  const max = Math.max(10, ...days.map((d) => d.xp_earned));
  const total = days.reduce((sum, d) => sum + d.xp_earned, 0);
  const active = days.filter((d) => d.puzzles_attempted > 0);

  return (
    <figure className="chart">
      <figcaption className="chart-caption">
        <span>
          {total} XP in the last {DAYS} days
        </span>
        <button
          type="button"
          className="link-button"
          onClick={() => setShowTable((v) => !v)}
          aria-expanded={showTable}
        >
          {showTable ? 'Show chart' : 'Show as table'}
        </button>
      </figcaption>

      {showTable ? (
        active.length ? (
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col">Attempted</th>
                <th scope="col">Solved</th>
                <th scope="col">XP</th>
              </tr>
            </thead>
            <tbody>
              {active.map((d) => (
                <tr key={d.date}>
                  <td>{formatDate(d.date)}</td>
                  <td>{d.puzzles_attempted}</td>
                  <td>{d.puzzles_solved}</td>
                  <td>{d.xp_earned}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="row-meta">No activity in the last {DAYS} days.</p>
        )
      ) : (
        <div
          className="bar-chart"
          role="img"
          aria-label={`Daily XP for the last ${DAYS} days, ${total} XP in total`}
        >
          <div className="bar-chart-axis" aria-hidden="true">
            <span>{max}</span>
            <span>0</span>
          </div>
          <div className="bar-chart-plot" onMouseLeave={() => setHover(null)}>
            {days.map((d, i) => (
              <div
                key={d.date}
                className="bar-slot"
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                tabIndex={d.puzzles_attempted ? 0 : -1}
                aria-label={`${formatDate(d.date)}: ${d.xp_earned} XP`}
              >
                <div className="bar" style={{ height: `${(d.xp_earned / max) * 100}%` }} />
              </div>
            ))}
            {hover !== null && (
              <div
                className="chart-tooltip"
                style={{ left: `${((hover + 0.5) / DAYS) * 100}%` }}
                role="status"
              >
                <strong>{formatDate(days[hover].date)}</strong>
                <span>{days[hover].xp_earned} XP</span>
                <span>
                  {days[hover].puzzles_solved} of {days[hover].puzzles_attempted} solved
                </span>
              </div>
            )}
          </div>
          <div className="bar-chart-dates" aria-hidden="true">
            <span>{formatDate(days[0].date)}</span>
            <span>Today</span>
          </div>
        </div>
      )}
    </figure>
  );
}
