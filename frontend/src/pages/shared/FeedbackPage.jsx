import { useState } from 'react';
import { errorMessage } from '../../features/trainer/api';
import { SelectField, TextArea } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  Empty,
  Loaded,
  PageHeader,
  Section,
  Status,
} from '../../features/trainer/components/ui';
import { formatDateTime } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { useRole } from './base';

const CATEGORIES = [
  { value: 'teaching', label: 'Teaching' },
  { value: 'content', label: 'Puzzles and content' },
  { value: 'scheduling', label: 'Scheduling' },
  { value: 'platform', label: 'The platform' },
  { value: 'other', label: 'Other' },
];

const BOXES = {
  student: [{ id: 'sent', label: 'Sent' }],
  trainer: [
    { id: 'inbox', label: 'From students' },
    { id: 'sent', label: 'Sent to admins' },
  ],
  admin: [
    { id: 'inbox', label: 'From trainers' },
    { id: 'all', label: 'All feedback' },
  ],
};

export default function FeedbackPage() {
  const role = useRole();
  const boxes = BOXES[role] ?? BOXES.student;
  const [box, setBox] = useState(boxes[0].id);
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const result = useLoader(
    () => sharedApi.feedback({ box, status: status || null, page, page_size: 20 }),
    [box, status, page],
  );

  const intro = {
    student: 'Tell your trainer what is working and what could be better.',
    trainer: 'Read what your students say, and send feedback to the academy admins.',
    admin: 'Feedback from trainers to the academy, and an overview of all feedback.',
  }[role];

  return (
    <TrainerPage>
      <PageHeader title="Feedback" subtitle={intro} />

      {role !== 'admin' && <SendFeedback role={role} onSent={result.reload} />}

      <div className="tr-tabs" role="tablist" aria-label="Feedback">
        {boxes.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className="tr-tab"
            aria-selected={box === item.id}
            onClick={() => {
              setBox(item.id);
              setPage(1);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="tr-filters">
        <SelectField
          label="Status"
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          placeholder="Any"
          options={[
            { value: 'open', label: 'Open' },
            { value: 'reviewed', label: 'Reviewed' },
          ]}
        />
      </div>

      <Loaded result={result}>
        {(data) =>
          data.items.length === 0 ? (
            <Empty title="No feedback here" />
          ) : (
            <>
              <ul className="feedback-list">
                {data.items.map((item) => (
                  <FeedbackItem key={item.id} item={item} onChanged={result.reload} />
                ))}
              </ul>
              <Pagination
                page={data.page}
                pages={data.pages}
                total={data.total}
                onChange={setPage}
                label="items"
              />
            </>
          )
        }
      </Loaded>
    </TrainerPage>
  );
}

function SendFeedback({ role, onSent }) {
  const recipients = useLoader(() => sharedApi.feedbackRecipients(), []);
  const [form, setForm] = useState({ to: '', message: '', category: '', rating: '' });
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await sharedApi.sendFeedback({
        to_user_id: role === 'student' ? form.to || recipients.data?.[0]?.id : null,
        message: form.message.trim(),
        category: form.category || null,
        rating: role === 'student' && form.rating ? Number(form.rating) : null,
      });
      setForm({ to: '', message: '', category: '', rating: '' });
      toast.success('Thank you — your feedback was sent.');
      onSent();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={role === 'student' ? 'Feedback for your trainer' : 'Feedback for the admins'}>
      <Loaded result={recipients}>
        {(list) =>
          list.length === 0 ? (
            <p className="tr-muted">
              You will be able to send feedback once a trainer is assigned.
            </p>
          ) : (
            <form className="tr-form" onSubmit={submit}>
              {role === 'student' && list.length > 1 && (
                <SelectField
                  label="Trainer"
                  required
                  value={form.to}
                  onChange={(to) => setForm({ ...form, to })}
                  placeholder="Choose a trainer"
                  options={list.map((item) => ({ value: item.id, label: item.name }))}
                />
              )}
              {role === 'student' && list.length === 1 && (
                <p className="tr-muted">To: {list[0].name}</p>
              )}
              <div className="tr-form-grid">
                <SelectField
                  label="Topic"
                  value={form.category}
                  onChange={(category) => setForm({ ...form, category })}
                  placeholder="Choose a topic"
                  options={CATEGORIES}
                />
                {role === 'student' && (
                  <SelectField
                    label="Rating"
                    value={form.rating}
                    onChange={(rating) => setForm({ ...form, rating })}
                    placeholder="No rating"
                    options={[5, 4, 3, 2, 1].map((n) => ({
                      value: String(n),
                      label: `${'★'.repeat(n)} (${n})`,
                    }))}
                  />
                )}
              </div>
              <TextArea
                label="Message"
                required
                rows={4}
                maxLength={5000}
                value={form.message}
                onChange={(message) => setForm({ ...form, message })}
              />
              <div>
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    form.message.trim().length < 3 ||
                    (role === 'student' && list.length > 1 && !form.to)
                  }
                >
                  {busy ? 'Sending…' : 'Send feedback'}
                </Button>
              </div>
            </form>
          )
        }
      </Loaded>
    </Section>
  );
}

function FeedbackItem({ item, onChanged }) {
  const [reply, setReply] = useState('');
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function review(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await sharedApi.reviewFeedback(item.id, reply.trim() || null);
      toast.success('Marked as reviewed.');
      onChanged();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="tr-card feedback-item">
      <div className="feedback-item__head">
        <strong>
          {item.from_name} → {item.to_name}
        </strong>
        <Status value={item.status === 'open' ? 'scheduled' : 'completed'} />
      </div>
      <p className="tr-muted">
        {formatDateTime(item.created_at)}
        {item.category
          ? ` · ${CATEGORIES.find((c) => c.value === item.category)?.label ?? item.category}`
          : ''}
        {item.rating ? ` · ${'★'.repeat(item.rating)}` : ''}
      </p>
      <p className="feedback-message">{item.message}</p>

      {item.status === 'reviewed' && (
        <div className="feedback-response">
          <p className="tr-muted">
            Reviewed by {item.reviewer_name} on {formatDateTime(item.reviewed_at)}
          </p>
          {item.response && <p>{item.response}</p>}
        </div>
      )}

      {item.status === 'open' && item.can_review && (
        <>
          {open ? (
            <form className="tr-form" onSubmit={review}>
              <TextArea
                label="Reply (optional)"
                rows={3}
                value={reply}
                onChange={setReply}
                maxLength={5000}
              />
              <div className="tr-page-actions">
                <Button type="submit" disabled={busy}>
                  {busy ? 'Saving…' : 'Mark as reviewed'}
                </Button>
                <Button variant="ghost" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <div>
              <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
                Review
              </Button>
            </div>
          )}
        </>
      )}
    </li>
  );
}
