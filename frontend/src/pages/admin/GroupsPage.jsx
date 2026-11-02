import { useState } from 'react';
import { Link, navigate, useRoute } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import { GroupDialog } from '../../features/admin/components/GroupDialogs';
import { ActiveStatus, UserLink } from '../../features/admin/components/shared';
import { STATUS_OPTIONS } from '../../features/admin/utils';
import DataTable from '../../features/trainer/components/DataTable';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import { Button, Empty, Loaded, PageHeader, Section } from '../../features/trainer/components/ui';
import { formatDate } from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';

export default function GroupsPage() {
  const { query: routeQuery } = useRoute();
  const [filters, setFilter] = useListState({
    search: '',
    is_active: null,
    trainer_id: routeQuery.trainer_id ?? null,
  });
  const [creating, setCreating] = useState(false);
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => adminApi.groups(query), [JSON.stringify(query)]);
  const trainers = useLoader(() => adminApi.trainers({ page_size: 100 }), []);
  const filtered = Boolean(filters.search || filters.is_active || filters.trainer_id);

  return (
    <AdminPage>
      <PageHeader
        title="Groups"
        subtitle="Create groups, assign their trainer and manage membership."
        actions={<Button onClick={() => setCreating(true)}>New group</Button>}
      />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search by group or trainer"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          <FilterSelect
            label="Trainer"
            value={filters.trainer_id}
            onChange={(value) => setFilter('trainer_id', value)}
            options={(trainers.data?.items ?? []).map((t) => ({ value: t.id, label: t.full_name }))}
          />
          <FilterSelect
            label="Status"
            value={filters.is_active}
            onChange={(value) => setFilter('is_active', value)}
            options={STATUS_OPTIONS}
          />
        </div>
        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <DataTable
                  caption="Groups"
                  rows={page.items}
                  columns={[
                    {
                      key: 'name',
                      label: 'Group',
                      render: (g) => (
                        <span className="tr-stack" style={{ gap: 2 }}>
                          <Link to={`/admin/groups/${g.id}`}>
                            <strong>{g.name}</strong>
                          </Link>
                          {g.description && <span className="tr-muted">{g.description}</span>}
                        </span>
                      ),
                    },
                    {
                      key: 'trainer',
                      label: 'Trainer',
                      render: (g) => <UserLink user={g.trainer} role="trainer" />,
                    },
                    { key: 'member_count', label: 'Students', align: 'right' },
                    {
                      key: 'is_active',
                      label: 'Status',
                      render: (g) => <ActiveStatus active={g.is_active} />,
                    },
                    {
                      key: 'created_at',
                      label: 'Created',
                      render: (g) => formatDate(g.created_at),
                    },
                  ]}
                />
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
                title={filtered ? 'No matching groups' : 'No groups yet'}
                message={
                  filtered
                    ? 'Try different filters.'
                    : 'Create a group and assign a trainer to start scheduling classes.'
                }
              />
            )
          }
        </Loaded>
      </Section>
      <GroupDialog
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={(group) => navigate(`/admin/groups/${group.id}`)}
      />
    </AdminPage>
  );
}
