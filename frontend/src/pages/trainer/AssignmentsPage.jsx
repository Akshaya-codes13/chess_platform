import { navigate } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import { formatDate, titleCase } from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import DataTable from '../../features/trainer/components/DataTable';
import Pagination from '../../features/trainer/components/Pagination';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import {
  ButtonLink,
  Empty,
  Loaded,
  Meter,
  PageHeader,
  Section,
  Status,
} from '../../features/trainer/components/ui';

export default function AssignmentsPage() {
  const [filters, setFilter] = useListState({
    search: '',
    status: null,
    group_id: null,
    sort: '-created_at',
  });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const groups = useLoader(() => trainerApi.groups({ page_size: 100 }), []);
  const result = useLoader(() => trainerApi.assignments(query), [JSON.stringify(query)]);

  return (
    <TrainerPage>
      <PageHeader
        title="Assignments"
        subtitle="Puzzle sets for your groups, from draft to completion."
        actions={<ButtonLink to="/trainer/assignments/new">New assignment</ButtonLink>}
      />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search titles"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(value) => setFilter('status', value)}
            options={['draft', 'published', 'completed', 'cancelled'].map((value) => ({
              value,
              label: titleCase(value),
            }))}
          />
          <FilterSelect
            label="Group"
            value={filters.group_id}
            onChange={(value) => setFilter('group_id', value)}
            options={
              groups.data?.items.map((group) => ({ value: group.id, label: group.name })) ?? []
            }
          />
        </div>
        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <DataTable
                  caption="Assignments"
                  rows={page.items}
                  sort={filters.sort}
                  onSort={(value) => setFilter('sort', value)}
                  onRowClick={(row) => navigate(`/trainer/assignments/${row.id}`)}
                  columns={[
                    {
                      key: 'title',
                      label: 'Title',
                      sortKey: 'title',
                      render: (row) => <strong>{row.title}</strong>,
                    },
                    { key: 'group', label: 'Group', render: (row) => row.group?.name ?? '—' },
                    {
                      key: 'status',
                      label: 'Status',
                      render: (row) => <Status value={row.status} />,
                    },
                    { key: 'puzzle_count', label: 'Puzzles', align: 'right' },
                    {
                      key: 'progress',
                      label: 'Completed',
                      render: (row) => (
                        <span className="tr-row">
                          <Meter
                            value={
                              row.recipient_count
                                ? (row.completed_count / row.recipient_count) * 100
                                : 0
                            }
                            label={`${row.title} completion`}
                          />
                          {row.completed_count}/{row.recipient_count}
                        </span>
                      ),
                    },
                    {
                      key: 'due_date',
                      label: 'Due',
                      sortKey: 'due_date',
                      render: (row) => formatDate(row.due_date),
                    },
                  ]}
                />
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label="assignments"
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty
                title={
                  filters.search || filters.status || filters.group_id
                    ? 'No matching assignments'
                    : 'No assignments yet'
                }
                action={
                  <ButtonLink to="/trainer/assignments/new" size="sm">
                    Create assignment
                  </ButtonLink>
                }
              />
            )
          }
        </Loaded>
      </Section>
    </TrainerPage>
  );
}
