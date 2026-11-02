import { useState } from 'react';
import { Link, useRoute } from '../../routes/router';
import { errorMessage, trainerApi } from '../../features/trainer/api';
import { formatTimeRange, titleCase } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
  StatCard,
  Status,
} from '../../features/trainer/components/ui';

const ATTENDANCE = ['present', 'late', 'absent', 'excused'];

const ACTIONS = {
  complete: [
    'Mark completed',
    'Mark this session as completed? You can still update attendance afterwards.',
    'primary',
    'completed',
  ],
  cancel: [
    'Cancel session',
    'Cancel this session? Cancelled sessions cannot be edited or have attendance recorded.',
    'danger',
    'cancelled',
  ],
};

export default function SessionDetailPage() {
  const { params } = useRoute();
  const result = useLoader(() => trainerApi.session(params.sessionId), [params.sessionId]);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);

  async function runAction() {
    setBusy(true);
    try {
      await trainerApi.sessionAction(params.sessionId, pending);
      toast.success(`Session ${ACTIONS[pending][3]}.`);
      result.reload();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(session) => {
          const active = ['scheduled', 'ongoing'].includes(session.status);
          const started = new Date(session.start_time) <= new Date();
          return (
            <>
              <PageHeader
                back={{ to: '/trainer/sessions', label: 'Sessions' }}
                title={session.title}
                subtitle={
                  <>
                    {session.group && (
                      <Link to={`/trainer/groups/${session.group.id}`}>{session.group.name}</Link>
                    )}
                    {' · '}
                    {formatTimeRange(session.start_time, session.end_time)}
                  </>
                }
                actions={
                  <>
                    <Status value={session.status} />
                    {session.can_edit && (
                      <ButtonLink to={`/trainer/sessions/${session.id}/edit`} variant="secondary">
                        Edit
                      </ButtonLink>
                    )}
                    {active && started && (
                      <Button onClick={() => setPending('complete')}>Mark completed</Button>
                    )}
                    {active && (
                      <Button variant="ghost" onClick={() => setPending('cancel')}>
                        Cancel session
                      </Button>
                    )}
                  </>
                }
              />

              <div className="tr-grid tr-grid--2">
                <Section title="About this session">
                  <dl className="tr-stack" style={{ margin: 0 }}>
                    <div>
                      <dt className="tr-field__label">Learning objective</dt>
                      <dd style={{ margin: 0 }}>{session.learning_objective || '—'}</dd>
                    </div>
                    <div>
                      <dt className="tr-field__label">Description</dt>
                      <dd style={{ margin: 0 }}>{session.description || '—'}</dd>
                    </div>
                    {session.meeting_url && (
                      <div>
                        <dt className="tr-field__label">Meeting link</dt>
                        <dd style={{ margin: 0 }}>
                          <a href={session.meeting_url} target="_blank" rel="noreferrer noopener">
                            {session.meeting_url}
                          </a>
                        </dd>
                      </div>
                    )}
                  </dl>
                </Section>
                <div className="tr-grid tr-grid--stats">
                  <StatCard label="Present" value={session.attendance_summary.present} />
                  <StatCard label="Late" value={session.attendance_summary.late} />
                  <StatCard label="Absent" value={session.attendance_summary.absent} />
                  <StatCard label="Excused" value={session.attendance_summary.excused} />
                  <StatCard label="Not recorded" value={session.attendance_summary.unrecorded} />
                </div>
              </div>

              <AttendanceEditor
                key={session.id + session.attendance_recorded}
                session={session}
                onSaved={result.reload}
              />

              <ConfirmDialog
                open={Boolean(pending)}
                title={pending ? `${ACTIONS[pending][0]}?` : ''}
                message={pending ? ACTIONS[pending][1] : ''}
                confirmLabel={pending ? ACTIONS[pending][0] : ''}
                tone={pending ? ACTIONS[pending][2] : 'primary'}
                busy={busy}
                onConfirm={runAction}
                onCancel={() => setPending(null)}
              />
            </>
          );
        }}
      </Loaded>
    </TrainerPage>
  );
}

function AttendanceEditor({ session, onSaved }) {
  const [marks, setMarks] = useState(() =>
    Object.fromEntries(
      session.roster.map((entry) => [
        entry.student_id,
        { status: entry.attendance_status, remarks: entry.remarks ?? '' },
      ]),
    ),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const changed = session.roster.filter((entry) => {
    const mark = marks[entry.student_id];
    return (
      mark.status &&
      (mark.status !== entry.attendance_status || (mark.remarks || '') !== (entry.remarks || ''))
    );
  });

  function update(studentId, patch) {
    setMarks((current) => ({ ...current, [studentId]: { ...current[studentId], ...patch } }));
  }

  function markAll(status) {
    setMarks((current) =>
      Object.fromEntries(
        Object.entries(current).map(([id, mark]) => [
          id,
          { ...mark, status: mark.status || status },
        ]),
      ),
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await trainerApi.recordAttendance(
        session.id,
        changed.map((entry) => ({
          student_id: entry.student_id,
          status: marks[entry.student_id].status,
          remarks: marks[entry.student_id].remarks.trim() || null,
        })),
      );
      toast.success(
        `Attendance saved for ${changed.length} student${changed.length === 1 ? '' : 's'}.`,
      );
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!session.roster.length) {
    return (
      <Section title="Attendance">
        <Empty title="This group has no students" />
      </Section>
    );
  }

  return (
    <Section
      title={`Attendance · ${session.roster.length} students`}
      actions={
        session.can_record_attendance && (
          <Button variant="ghost" size="sm" onClick={() => markAll('present')}>
            Mark unrecorded as present
          </Button>
        )
      }
    >
      {!session.can_record_attendance && (
        <p className="tr-callout tr-callout--info">
          {session.status === 'cancelled'
            ? 'Attendance cannot be recorded for a cancelled session.'
            : 'Attendance can be recorded once the session has started.'}
        </p>
      )}
      {error && (
        <p className="tr-callout tr-callout--error" role="alert">
          {error}
        </p>
      )}
      <div>
        {session.roster.map((entry) => {
          const mark = marks[entry.student_id];
          return (
            <div key={entry.student_id} className="tr-attendance-row">
              <span>
                <Link to={`/trainer/students/${entry.student_id}`}>
                  <strong>{entry.full_name}</strong>
                </Link>
                <br />
                <span className="tr-muted" style={{ fontSize: '0.85rem' }}>
                  {entry.email}
                </span>
              </span>
              {session.can_record_attendance ? (
                <div
                  className="tr-segmented"
                  role="radiogroup"
                  aria-label={`Attendance for ${entry.full_name}`}
                >
                  {ATTENDANCE.map((status) => (
                    <label key={status}>
                      <input
                        type="radio"
                        name={`attendance-${entry.student_id}`}
                        value={status}
                        checked={mark.status === status}
                        onChange={() => update(entry.student_id, { status })}
                      />
                      <span>{titleCase(status)}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <Status value={entry.attendance_status} />
              )}
              {session.can_record_attendance ? (
                <input
                  className="tr-input tr-input--sm"
                  aria-label={`Remarks for ${entry.full_name}`}
                  placeholder="Remarks (optional)"
                  maxLength={500}
                  value={mark.remarks}
                  onChange={(event) => update(entry.student_id, { remarks: event.target.value })}
                />
              ) : (
                <span className="tr-muted">{entry.remarks || ''}</span>
              )}
            </div>
          );
        })}
      </div>
      {session.can_record_attendance && (
        <div className="tr-form-actions" style={{ marginTop: 14 }}>
          <span className="tr-muted" style={{ marginRight: 'auto', alignSelf: 'center' }}>
            {changed.length
              ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}`
              : 'No unsaved changes'}
          </span>
          <Button disabled={!changed.length || saving} onClick={save}>
            {saving ? 'Saving…' : 'Save attendance'}
          </Button>
        </div>
      )}
    </Section>
  );
}
