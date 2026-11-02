import { Link } from '../../routes/router';
import { adminApi } from '../../features/admin/api';
import AdminPage from '../../features/admin/components/AdminPage';
import DataTable from '../../features/trainer/components/DataTable';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import { Empty, Loaded, PageHeader, Section, Status } from '../../features/trainer/components/ui';
import { titleCase } from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';

const toOptions = (values) => values.map((value) => ({ value, label: titleCase(value) }));

export default function PuzzlesPage() {
  const [filters, setFilter] = useListState({
    search: '',
    status: null,
    category_id: null,
    theme_id: null,
    type: null,
    source: null,
    incomplete_only: null,
  });
  const search = useDebounced(filters.search);
  const query = { ...filters, search };
  const result = useLoader(() => adminApi.puzzles(query), [JSON.stringify(query)]);
  const options = useLoader(() => adminApi.puzzleFilters(), []);
  const meta = options.data;

  return (
    <AdminPage>
      <PageHeader
        title="Puzzles"
        subtitle="Every puzzle on the platform, including trainers' drafts. Records with problems are flagged."
      />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search ID, difficulty or explanation"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(value) => setFilter('status', value)}
            options={toOptions(meta?.statuses ?? ['draft', 'published', 'archived'])}
          />
          <FilterSelect
            label="Category"
            value={filters.category_id}
            onChange={(value) => setFilter('category_id', value)}
            options={(meta?.categories ?? []).map((c) => ({ value: c.id, label: c.name }))}
          />
          <FilterSelect
            label="Theme"
            value={filters.theme_id}
            onChange={(value) => setFilter('theme_id', value)}
            options={(meta?.themes ?? []).map((t) => ({ value: t.id, label: t.name }))}
          />
          <FilterSelect
            label="Type"
            value={filters.type}
            onChange={(value) => setFilter('type', value)}
            options={toOptions(meta?.types ?? [])}
          />
          <FilterSelect
            label="Source"
            value={filters.source}
            onChange={(value) => setFilter('source', value)}
            options={toOptions(meta?.sources ?? [])}
          />
          <FilterSelect
            label="Completeness"
            value={filters.incomplete_only}
            onChange={(value) => setFilter('incomplete_only', value)}
            allLabel="All puzzles"
            options={[{ value: 'true', label: 'Missing data only' }]}
          />
        </div>
        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <DataTable
                  caption="Puzzles"
                  rows={page.items}
                  columns={[
                    {
                      key: 'id',
                      label: 'Puzzle',
                      render: (p) => (
                        <span className="tr-stack" style={{ gap: 2 }}>
                          <Link to={`/admin/puzzles/${p.id}`}>
                            <strong>{p.lichess_id ?? `#${p.id.slice(0, 8)}`}</strong>
                          </Link>
                          <span className="tr-muted">
                            {titleCase(p.type)} · {p.source}
                            {p.author && ` · by ${p.author.full_name}`}
                          </span>
                        </span>
                      ),
                    },
                    { key: 'status', label: 'Status', render: (p) => <Status value={p.status} /> },
                    {
                      key: 'rating',
                      label: 'Rating',
                      align: 'right',
                      render: (p) => p.rating ?? '—',
                    },
                    {
                      key: 'category',
                      label: 'Category',
                      render: (p) => p.category?.name ?? <span className="tr-muted">—</span>,
                    },
                    {
                      key: 'themes',
                      label: 'Themes',
                      render: (p) =>
                        p.themes.length ? (
                          p.themes.map((t) => t.name).join(', ')
                        ) : (
                          <span className="tr-muted">—</span>
                        ),
                    },
                    {
                      key: 'issues',
                      label: 'Issues',
                      render: (p) =>
                        p.issues.length ? (
                          <span className="tr-pill tr-pill--warning" title={p.issues.join(' ')}>
                            {p.issues.length} issue{p.issues.length === 1 ? '' : 's'}
                          </span>
                        ) : (
                          <span className="tr-muted">None</span>
                        ),
                    },
                  ]}
                />
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label="puzzles"
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty title="No puzzles match" message="Try different filters." />
            )
          }
        </Loaded>
      </Section>
    </AdminPage>
  );
}
