/**
 * Responsive table: a normal table on wide screens, stacked cards on narrow
 * ones (each cell carries its column label via data-label).
 *
 * columns: [{ key, label, render?(row), sortKey?, align? }]
 * sort: current sort string, where "-key" means descending.
 */
export default function DataTable({
  columns,
  rows,
  rowKey = 'id',
  sort,
  onSort,
  onRowClick,
  caption,
}) {
  return (
    <div className="tr-table-wrap">
      <table className="tr-table">
        {caption && <caption className="tr-visually-hidden">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={{ textAlign: column.align }}
                aria-sort={ariaSort(column, sort)}
              >
                {column.sortKey && onSort ? (
                  <button
                    type="button"
                    className="tr-sort"
                    onClick={() => onSort(nextSort(column.sortKey, sort))}
                  >
                    {column.label}
                    <span aria-hidden="true">{sortIndicator(column.sortKey, sort)}</span>
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row[rowKey]}
              className={onRowClick ? 'tr-table__row--link' : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td key={column.key} data-label={column.label} style={{ textAlign: column.align }}>
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function nextSort(key, sort) {
  return sort === key ? `-${key}` : key;
}

function sortIndicator(key, sort) {
  if (sort === key) return ' ▲';
  if (sort === `-${key}`) return ' ▼';
  return '';
}

function ariaSort(column, sort) {
  if (!column.sortKey) return undefined;
  if (sort === column.sortKey) return 'ascending';
  if (sort === `-${column.sortKey}`) return 'descending';
  return 'none';
}
