import { Link } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import { formatDate } from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import Pagination from '../../features/trainer/components/Pagination';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import { Empty, Loaded, PageHeader, Section, Status } from '../../features/trainer/components/ui';

export default function GroupsPage() {
  const [filters, setFilter] = useListState({ search: '', is_active: null, page_size: 12 });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => trainerApi.groups(query), [JSON.stringify(query)]);

  return (
    <TrainerPage>
      <PageHeader title="My groups" subtitle="Groups assigned to you by an administrator." />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search groups"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          <FilterSelect
            label="Status"
            value={filters.is_active}
            onChange={(value) => setFilter('is_active', value)}
            options={[
              { value: 'true', label: 'Active' },
              { value: 'false', label: 'Inactive' },
            ]}
          />
        </div>
        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <div className="tr-grid tr-grid--cards">
                  {page.items.map((group) => (
                    <Link
                      key={group.id}
                      to={`/trainer/groups/${group.id}`}
                      className="tr-puzzle-card"
                      style={{ flexDirection: 'column' }}
                    >
                      <span className="tr-row" style={{ justifyContent: 'space-between' }}>
                        <strong>{group.name}</strong>
                        <Status value={group.is_active ? 'active' : 'inactive'} />
                      </span>
                      {group.description && <span className="tr-muted">{group.description}</span>}
                      <span className="tr-muted">
                        {group.student_count} students · since {formatDate(group.created_at)}
                      </span>
                    </Link>
                  ))}
                </div>
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label="groups"
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty
                title={
                  filters.search || filters.is_active
                    ? 'No matching groups'
                    : 'No groups assigned yet'
                }
                message={
                  filters.search || filters.is_active
                    ? 'Try different filters.'
                    : 'An administrator assigns groups to trainers.'
                }
              />
            )
          }
        </Loaded>
      </Section>
    </TrainerPage>
  );
}
