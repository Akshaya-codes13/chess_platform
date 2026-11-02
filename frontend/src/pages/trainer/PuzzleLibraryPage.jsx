import { Link } from '../../routes/router';
import { trainerApi } from '../../features/trainer/api';
import { DIFFICULTIES, sideToMove, titleCase } from '../../features/trainer/format';
import { useDebounced, useListState, useLoader } from '../../features/trainer/hooks';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import FenBoard from '../../features/trainer/components/FenBoard';
import Pagination from '../../features/trainer/components/Pagination';
import { FilterSelect, SearchInput } from '../../features/trainer/components/Field';
import {
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Section,
  Status,
} from '../../features/trainer/components/ui';

export default function PuzzleLibraryPage() {
  const [filters, setFilter] = useListState({
    search: '',
    ownership: 'all',
    difficulty: null,
    category_id: null,
    theme_id: null,
    status: null,
    rating_min: '',
    rating_max: '',
    sort: '-created_at',
    page_size: 12,
  });
  const search = useDebounced(filters.search);
  const ratingMin = useDebounced(filters.rating_min);
  const ratingMax = useDebounced(filters.rating_max);
  const query = { ...filters, search, rating_min: ratingMin, rating_max: ratingMax };

  const taxonomy = useLoader(() => trainerApi.taxonomy(), []);
  const result = useLoader(() => trainerApi.puzzles(query), [JSON.stringify(query)]);

  const categories = taxonomy.data?.categories.map((c) => ({ value: c.id, label: c.name })) ?? [];
  const themes = taxonomy.data?.themes.map((t) => ({ value: t.id, label: t.name })) ?? [];

  return (
    <TrainerPage>
      <PageHeader
        title="Puzzle library"
        subtitle="Published academy puzzles and every puzzle you have created."
        actions={<ButtonLink to="/trainer/puzzles/new">Create puzzle</ButtonLink>}
      />
      <Section>
        <div className="tr-filters">
          <SearchInput
            label="Search"
            placeholder="Explanation or source id"
            value={filters.search}
            onChange={(value) => setFilter('search', value)}
          />
          <FilterSelect
            label="Show"
            value={filters.ownership === 'all' ? null : filters.ownership}
            onChange={(value) => setFilter('ownership', value || 'all')}
            allLabel="All puzzles"
            options={[
              { value: 'mine', label: 'Created by me' },
              { value: 'library', label: 'Academy library' },
            ]}
          />
          <FilterSelect
            label="Difficulty"
            value={filters.difficulty}
            onChange={(value) => setFilter('difficulty', value)}
            options={DIFFICULTIES}
          />
          <FilterSelect
            label="Category"
            value={filters.category_id}
            onChange={(value) => setFilter('category_id', value)}
            options={categories}
          />
          <FilterSelect
            label="Theme"
            value={filters.theme_id}
            onChange={(value) => setFilter('theme_id', value)}
            options={themes}
          />
          <FilterSelect
            label="Status"
            value={filters.status}
            onChange={(value) => setFilter('status', value)}
            options={['published', 'draft', 'archived'].map((value) => ({
              value,
              label: titleCase(value),
            }))}
          />
          <div className="tr-filter" style={{ minWidth: 90 }}>
            <label className="tr-filter__label" htmlFor="rating-min">
              Min rating
            </label>
            <input
              id="rating-min"
              type="number"
              min="0"
              max="4000"
              className="tr-input tr-input--sm"
              value={filters.rating_min}
              onChange={(event) => setFilter('rating_min', event.target.value)}
            />
          </div>
          <div className="tr-filter" style={{ minWidth: 90 }}>
            <label className="tr-filter__label" htmlFor="rating-max">
              Max rating
            </label>
            <input
              id="rating-max"
              type="number"
              min="0"
              max="4000"
              className="tr-input tr-input--sm"
              value={filters.rating_max}
              onChange={(event) => setFilter('rating_max', event.target.value)}
            />
          </div>
          <FilterSelect
            label="Sort by"
            value={filters.sort}
            onChange={(value) => setFilter('sort', value || '-created_at')}
            allLabel="Newest first"
            options={[
              { value: 'created_at', label: 'Oldest first' },
              { value: 'rating', label: 'Rating: low to high' },
              { value: '-rating', label: 'Rating: high to low' },
            ]}
          />
        </div>

        <Loaded result={result}>
          {(page) =>
            page.items.length ? (
              <>
                <div className="tr-grid tr-grid--cards">
                  {page.items.map((puzzle) => (
                    <Link
                      key={puzzle.id}
                      to={`/trainer/puzzles/${puzzle.id}`}
                      className="tr-puzzle-card"
                    >
                      <FenBoard
                        fen={puzzle.fen}
                        size="sm"
                        flipped={sideToMove(puzzle.fen) === 'Black'}
                      />
                      <span className="tr-puzzle-card__meta">
                        <strong>{puzzle.rating ? `Rating ${puzzle.rating}` : 'Unrated'}</strong>
                        <span className="tr-muted">
                          {sideToMove(puzzle.fen)} to move ·{' '}
                          {titleCase(puzzle.difficulty) || 'No difficulty'}
                        </span>
                        {puzzle.category && (
                          <span className="tr-muted">{puzzle.category.name}</span>
                        )}
                        <span className="tr-tags">
                          {puzzle.themes.map((theme) => (
                            <span key={theme.id} className="tr-tag">
                              {theme.name}
                            </span>
                          ))}
                        </span>
                        <span className="tr-row">
                          <Status value={puzzle.status} />
                          {puzzle.is_owner && <span className="tr-tag">Yours</span>}
                        </span>
                      </span>
                    </Link>
                  ))}
                </div>
                <Pagination
                  page={page.page}
                  pages={page.pages}
                  total={page.total}
                  label="puzzles"
                  onChange={(value) => setFilter('page', value)}
                />
              </>
            ) : (
              <Empty
                title="No puzzles match these filters"
                action={
                  <ButtonLink to="/trainer/puzzles/new" size="sm">
                    Create puzzle
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
