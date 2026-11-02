export default function ProgressBar({ value, label, tone = 'default' }) {
  const clamped = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className={`progress progress-${tone}`}>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped)}
        aria-label={label}
      >
        <div className="progress-fill" style={{ width: `${clamped}%` }} />
      </div>
      {label && <span className="progress-label">{label}</span>}
    </div>
  );
}
