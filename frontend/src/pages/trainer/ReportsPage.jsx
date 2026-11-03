import { useState } from 'react';
import { DailyBarChart, DailyLineChart } from '../../components/charts/DailyCharts';
import { ConsistencyTable, FreshnessNote, RangeTabs } from '../../components/charts/ReportParts';
import { trainerApi } from '../../features/trainer/api';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { Loaded, PageHeader, Section, StatCard } from '../../features/trainer/components/ui';
import { formatPercent } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { navigate } from '../../routes/router';

export default function ReportsPage() {
  const [days, setDays] = useState(30);
  const result = useLoader(() => trainerApi.dailyReport(days), [days]);

  return (
    <TrainerPage>
      <PageHeader
        title="Reports"
        subtitle="Your classes, attendance, submissions and how consistently your students practise."
      />
      <RangeTabs value={days} onChange={setDays} />
      <Loaded result={result}>
        {(report) => (
          <>
            <FreshnessNote report={report} />
            <div className="tr-grid tr-grid--stats">
              <StatCard label="Sessions held" value={report.totals.sessions_held} />
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
            </div>

            <Section title="Activity">
              <div className="chart-grid">
                <DailyLineChart
                  title="Puzzle attempts on your assignments"
                  data={report.series}
                  series={[
                    { key: 'puzzle_attempts', label: 'Attempts' },
                    { key: 'puzzles_solved', label: 'Solved' },
                  ]}
                />
                <DailyBarChart
                  title="Attendance at your sessions"
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
                  title="Submissions received"
                  data={report.series}
                  series={[{ key: 'submissions', label: 'Submissions' }]}
                />
                <DailyLineChart
                  title="Students practising on your assignments"
                  data={report.series}
                  series={[{ key: 'active_students', label: 'Active students' }]}
                />
              </div>
            </Section>

            <ConsistencyTable
              students={report.students}
              days={report.days}
              onOpen={(row) => navigate(`/trainer/students/${row.student_id}`)}
            />
          </>
        )}
      </Loaded>
    </TrainerPage>
  );
}
