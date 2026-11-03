const shortDate = (value) =>
  new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

/**
 * GitHub-style consistency calendar: one cell per day, darker = more puzzles
 * attempted. One hue (the app accent) from light to dark.
 */
export default function ConsistencyCalendar({ days, title = 'Practice consistency' }) {
  const max = Math.max(1, ...days.map((day) => day.puzzles_attempted));
  const level = (count) => (count === 0 ? 0 : Math.min(4, Math.ceil((count / max) * 4)));
  const leading = (new Date(`${days[0]?.date}T00:00:00Z`).getUTCDay() + 6) % 7; // Monday first
  const cells = [...Array(leading).fill(null), ...days];

  return (
    <figure className="chart">
      <figcaption className="chart-title">{title}</figcaption>
      <div
        className="calendar-grid"
        role="img"
        aria-label={`${title}: ${days.filter((d) => d.puzzles_attempted).length} active days out of ${days.length}`}
      >
        {cells.map((day, index) =>
          day ? (
            <span
              key={day.date}
              className={`calendar-cell level-${level(day.puzzles_attempted)}`}
              title={`${shortDate(day.date)}: ${day.puzzles_attempted} attempted, ${day.puzzles_solved} solved, ${day.xp_earned} XP`}
            />
          ) : (
            <span key={`pad-${index}`} className="calendar-cell is-pad" aria-hidden="true" />
          ),
        )}
      </div>
      <div className="calendar-legend" aria-hidden="true">
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((step) => (
          <span key={step} className={`calendar-cell level-${step}`} />
        ))}
        <span>More</span>
      </div>
    </figure>
  );
}
