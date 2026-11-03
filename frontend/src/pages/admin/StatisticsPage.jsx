import { useState } from 'react';
import { DailyBarChart, DailyLineChart } from '../../components/charts/DailyCharts';
import { ConsistencyTable, FreshnessNote, RangeTabs } from '../../components/charts/ReportParts';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import { errorMessage } from '../../features/trainer/api';
import DataTable from '../../features/trainer/components/DataTable';
import { toast } from '../../features/trainer/components/toastStore';
import {
  Button,
  Loaded,
  PageHeader,
  Section,
  StatCard,
} from '../../features/trainer/components/ui';
import { formatPercent } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { navigate } from '../../routes/router';

/**
 * Academy statistics from the precomputed daily summary tables (written by
 * the ARQ worker). Every figure is a sum of stored daily rows.
 */
export default function StatisticsPage() {
  const [days, setDays] = useState(30);
  const [refreshing, setRefreshing] = useState(false);
  const result = useLoader(() => adminApi.dailyReport(days), [days]);

  async function refresh() {
    setRefreshing(true);
    try {
      const outcome = await adminApi.refreshDailyReport();
      toast.success(
        outcome.queued
          ? 'Recalculation queued; reload in a few seconds.'
          : "Today's figures were recalculated.",
      );
      setTimeout(result.reload, outcome.queued ? 3000 : 0);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <AdminPage>
      <PageHeader
        title="Statistics"
        subtitle="Classes, attendance, submissions and practice across the academy."
        actions={
          <Button variant="secondary" onClick={refresh} disabled={refreshing}>
            {refreshing ? 'Queuing…' : 'Recalculate now'}
          </Button>
        }
      />
      <RangeTabs value={days} onChange={setDays} />
      <Loaded result={result}>
        {(report) => (
          <>
            <FreshnessNote report={report} />
            <div className="tr-grid tr-grid--stats">
              <StatCard label="Classes held" value={report.totals.sessions_held} />
              <StatCard
                label="Attendance rate"
                value={formatPercent(report.totals.attendance_rate)}
              />
              <StatCard label="Submissions" value={report.totals.submissions} />
              <StatCard
                label="Puzzles solved"
                value={report.totals.puzzles_solved}
                hint={`${formatPercent(report.totals.solve_rate)} of ${report.totals.puzzle_attempts} attempts`}
              />
              <StatCard label="XP awarded" value={report.totals.xp_awarded} />
              <StatCard
                label="New accounts"
                value={report.totals.new_students + report.totals.new_trainers}
                hint={`${report.totals.new_students} students · ${report.totals.new_trainers} trainers`}
              />
            </div>

            <Section title="Daily activity">
              <div className="chart-grid">
                <DailyLineChart
                  title="Students practising per day"
                  data={report.series}
                  series={[{ key: 'active_students', label: 'Active students' }]}
                />
                <DailyLineChart
                  title="Puzzle attempts"
                  data={report.series}
                  series={[
                    { key: 'puzzle_attempts', label: 'Attempts' },
                    { key: 'puzzles_solved', label: 'Solved' },
                  ]}
                />
                <DailyBarChart
                  title="Attendance"
                  stacked
                  data={report.series}
                  series={[
                    { key: 'attendance_present', label: 'Present' },
                    { key: 'attendance_late', label: 'Late' },
                    { key: 'attendance_absent', label: 'Absent' },
                    { key: 'attendance_excused', label: 'Excused' },
                  ]}
                />
                <DailyBarChart
                  title="Classes and submissions"
                  data={report.series}
                  series={[
                    { key: 'sessions_held', label: 'Classes held' },
                    { key: 'submissions', label: 'Submissions' },
                  ]}
                />
              </div>
            </Section>

            <Section title="Trainers">
              <DataTable
                caption="Totals per trainer"
                rowKey="trainer_id"
                rows={report.trainers}
                columns={[
                  {
                    key: 'full_name',
                    label: 'Trainer',
                    render: (row) => <strong>{row.full_name}</strong>,
                  },
                  { key: 'sessions_held', label: 'Classes', align: 'right' },
                  {
                    key: 'attendance_rate',
                    label: 'Attendance',
                    align: 'right',
                    render: (row) => formatPercent(row.attendance_rate),
                  },
                  { key: 'submissions', label: 'Submissions', align: 'right' },
                  { key: 'active_students', label: 'Student-days active', align: 'right' },
                  {
                    key: 'solve_rate',
                    label: 'Solve rate',
                    align: 'right',
                    render: (row) => formatPercent(row.solve_rate),
                  },
                ]}
              />
            </Section>

            <ConsistencyTable
              students={report.students}
              days={report.days}
              onOpen={(row) => navigate(`/admin/students/${row.user_id}`)}
            />
          </>
        )}
      </Loaded>
    </AdminPage>
  );
}
