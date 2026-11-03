import DataTable from '../../features/trainer/components/DataTable';
import { Meter, Section } from '../../features/trainer/components/ui';
import { formatDateTime } from '../../features/trainer/format';

const RANGES = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
];

export function RangeTabs({ value, onChange }) {
  return (
    <div className="tr-tabs" role="tablist" aria-label="Date range">
      {RANGES.map((range) => (
        <button
          key={range.days}
          type="button"
          role="tab"
          className="tr-tab"
          aria-selected={value === range.days}
          onClick={() => onChange(range.days)}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}

export function FreshnessNote({ report }) {
  return (
    <p className="tr-muted">
      From the daily summary tables, last computed {formatDateTime(report.last_computed_at)}.
      {report.missing_days.length > 0 &&
        ` ${report.missing_days.length} day(s) are not computed yet and are shown as zero.`}
    </p>
  );
}

export function ConsistencyTable({ students, days, onOpen }) {
  return (
    <Section title="Student consistency">
      <DataTable
        caption="Active days per student"
        rowKey="student_id"
        rows={students}
        onRowClick={onOpen}
        columns={[
          { key: 'full_name', label: 'Student', render: (row) => <strong>{row.full_name}</strong> },
          {
            key: 'active_days',
            label: `Active days (of ${days})`,
            render: (row) => (
              <span className="tr-row">
                <Meter
                  value={row.consistency_percent ?? 0}
                  label={`${row.full_name} consistency`}
                />
                {row.active_days}
              </span>
            ),
          },
          { key: 'puzzles_solved', label: 'Puzzles solved', align: 'right' },
          { key: 'xp_earned', label: 'XP earned', align: 'right' },
        ]}
      />
    </Section>
  );
}
