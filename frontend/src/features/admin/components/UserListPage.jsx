import { useState } from 'react';
import { navigate, useRoute } from '../../../routes/router';
import DataTable from '../../trainer/components/DataTable';
import { FilterSelect, SearchInput } from '../../trainer/components/Field';
import Pagination from '../../trainer/components/Pagination';
import { Button, Empty, Loaded, PageHeader, Section } from '../../trainer/components/ui';
import { useDebounced, useListState, useLoader } from '../../trainer/hooks';
import { STATUS_OPTIONS, userPath } from '../utils';
import AdminPage from './AdminPage';
import { AccountDialog } from './UserDialogs';

/**
 * Searchable, filterable, paginated list of accounts.
 *
 * load(query) fetches a page; filters are extra FilterSelect definitions
 * ({ name, label, options }); createRole enables the "New …" dialog.
 */
export default function UserListPage({
  title,
  subtitle,
  noun,
  load,
  columns,
  filters: extraFilters = [],
  createRole,
  createLabel,
}) {
  const { query: routeQuery } = useRoute();
  const initial = Object.fromEntries(
    extraFilters.map((filter) => [filter.name, routeQuery[filter.name] ?? null]),
  );
  const [filters, setFilter] = useListState({ search: '', is_active: null, ...initial });
  const [creating, setCreating] = useState(false);
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => load(query), [JSON.stringify(query)]);
  const filtered = Boolean(
    filters.search || filters.is_active || extraFilters.some((f) => filters[f.name]),
  );

  return (
    <AdminPage>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          createRole !== undefined && (
            <Button onClick={() => setCreating(true)}>{createLabel ?? `New ${noun}`}</Button>
          )
        }
      />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search by name or email"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          {extraFilters.map((filter) => (
            <FilterSelect
              key={filter.name}
              label={filter.label}
              value={filters[filter.name]}
              onChange={(value) => setFilter(filter.name, value)}
              options={filter.options}
            />
          ))}
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
                <DataTable caption={title} columns={columns} rows={page.items} />
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label={`${noun}s`}
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty
                title={filtered ? `No matching ${noun}s` : `No ${noun}s yet`}
                message={filtered ? 'Try different search terms or filters.' : undefined}
              />
            )
          }
        </Loaded>
      </Section>
      {createRole !== undefined && (
        <AccountDialog
          open={creating}
          role={createRole}
          onClose={() => setCreating(false)}
          onCreated={(user) => navigate(userPath(user))}
        />
      )}
    </AdminPage>
  );
}
