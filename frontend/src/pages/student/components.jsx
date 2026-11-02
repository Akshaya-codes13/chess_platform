import ProgressBar from '../../components/ui/ProgressBar';
import StatusBadge from '../../components/ui/StatusBadge';
import { dueLabel, formatDateTime, formatSessionTime, titleCase } from '../../lib/format';
import { Link } from '../../routes/router';

export function AssignmentRow({ assignment }) {
  const { progress } = assignment;
  return (
    <li className="row-item">
      <Link to={`/student/assignments/${assignment.id}`} className="row-link">
        <div className="row-main">
          <span className="row-title">{assignment.title}</span>
          <span className="row-meta">
            {assignment.group_name ?? 'Individual'} · {assignment.trainer_name}
          </span>
        </div>
        <div className="row-side">
          <StatusBadge status={assignment.status} />
          <span className={`row-due ${assignment.status === 'overdue' ? 'is-warning' : ''}`}>
            {dueLabel(assignment.due_date, assignment.status)}
          </span>
        </div>
        <ProgressBar
          value={progress.completion_percent}
          label={`${progress.completed_puzzles} of ${progress.total_puzzles} puzzles`}
          tone={assignment.status === 'completed' ? 'success' : 'default'}
        />
      </Link>
    </li>
  );
}

export function SessionRow({ session }) {
  const start = new Date(session.start_time);
  return (
    <li className="row-item">
      <Link to={`/student/sessions/${session.id}`} className="row-link session-row">
        <time className="date-chip" dateTime={session.start_time}>
          <span className="date-chip-day">{start.getDate()}</span>
          <span className="date-chip-month">
            {start.toLocaleString(undefined, { month: 'short' })}
          </span>
        </time>
        <div className="row-main">
          <span className="row-title">{session.title}</span>
          <span className="row-meta">
            {formatSessionTime(session.start_time, session.end_time)} · {session.trainer_name}
          </span>
        </div>
        <div className="row-side">
          {session.status === 'cancelled' ? (
            <StatusBadge status="cancelled" />
          ) : session.attendance_status && !session.is_upcoming ? (
            <StatusBadge status={session.attendance_status} />
          ) : (
            <span className="row-meta">
              {session.group_name ?? titleCase(session.session_type)}
            </span>
          )}
        </div>
      </Link>
    </li>
  );
}

export function AttemptRow({ attempt }) {
  return (
    <li className="attempt-row">
      <span
        className={`attempt-mark ${attempt.is_solved ? 'is-solved' : 'is-missed'}`}
        aria-hidden="true"
      />
      <span className="row-main">
        <span className="row-title">
          {attempt.is_solved ? 'Solved' : 'Missed'}
          {attempt.rating ? ` a ${attempt.rating} puzzle` : ' a puzzle'}
        </span>
        <span className="row-meta">
          {[attempt.themes.join(', '), attempt.assignment_title].filter(Boolean).join(' · ')}
        </span>
      </span>
      <time className="row-meta" dateTime={attempt.attempted_at}>
        {formatDateTime(attempt.attempted_at)}
      </time>
    </li>
  );
}

/** A horizontal strip of figures; each item is { label, value, hint }. */
export function StatStrip({ items }) {
  return (
    <dl className="stat-strip">
      {items.map((item) => (
        <div key={item.label} className={`stat ${item.tone ? `stat-${item.tone}` : ''}`}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
          {item.hint && <span className="stat-hint">{item.hint}</span>}
        </div>
      ))}
    </dl>
  );
}

export function BadgeTile({ badge }) {
  return (
    <li className={`badge-tile ${badge.earned ? 'is-earned' : 'is-locked'}`}>
      <span className="badge-medal" aria-hidden="true">
        {badge.icon_url ? <img src={badge.icon_url} alt="" /> : '♛︎'}
      </span>
      <span className="badge-name">{badge.name}</span>
      {badge.description && <span className="badge-description">{badge.description}</span>}
      <span className="badge-meta">
        {badge.earned
          ? `Earned ${formatDateTime(badge.earned_at)}`
          : `Not earned yet${badge.xp_reward ? ` · ${badge.xp_reward} XP` : ''}`}
      </span>
    </li>
  );
}

export function MilestoneMeter({ milestone }) {
  if (!milestone)
    return <p className="row-meta">You have earned every badge available right now.</p>;
  const percent = (milestone.current / milestone.target) * 100;
  return (
    <div className="milestone">
      <p>
        <strong>{milestone.badge_name}</strong>
        {milestone.description ? ` — ${milestone.description}` : ''}
      </p>
      <ProgressBar
        value={percent}
        label={`${milestone.current} of ${milestone.target}`}
        tone="reward"
      />
    </div>
  );
}

export function TrainerCard({ trainer }) {
  if (!trainer) return null;
  return (
    <div className="trainer">
      <span className="avatar" aria-hidden="true">
        {trainer.avatar_url ? <img src={trainer.avatar_url} alt="" /> : trainer.full_name.charAt(0)}
      </span>
      <div>
        <p className="row-title">{trainer.full_name}</p>
        <p className="row-meta">
          {[
            trainer.specialization,
            trainer.experience_years ? `${trainer.experience_years} years coaching` : null,
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
        {trainer.bio && <p className="trainer-bio">{trainer.bio}</p>}
      </div>
    </div>
  );
}
