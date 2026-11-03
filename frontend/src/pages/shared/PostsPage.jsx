import { useState } from 'react';
import { apiUrl } from '../../api/client';
import { SearchInput } from '../../features/trainer/components/Field';
import Pagination from '../../features/trainer/components/Pagination';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import {
  ButtonLink,
  Empty,
  Loaded,
  PageHeader,
  Status,
} from '../../features/trainer/components/ui';
import { formatDate } from '../../features/trainer/format';
import { useDebounced, useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { Link } from '../../routes/router';
import { usePortalBase, useRole } from './base';

const TABS = [
  { id: 'all', label: 'All', query: {} },
  { id: 'article', label: 'Articles', query: { type: 'article' } },
  { id: 'blog', label: 'Blogs', query: { type: 'blog' } },
  { id: 'photo', label: 'Gallery', query: { type: 'photo' } },
];

export default function PostsPage() {
  const base = usePortalBase();
  const role = useRole();
  const canWrite = role === 'admin' || role === 'trainer';
  const [tab, setTab] = useState('all');
  const [mine, setMine] = useState(false);
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search.trim());
  const [page, setPage] = useState(1);
  const active = TABS.find((item) => item.id === tab);
  const result = useLoader(
    () =>
      sharedApi.posts({
        ...active.query,
        mine: mine || null,
        search: debounced || null,
        page,
        page_size: tab === 'photo' ? 24 : 12,
      }),
    [tab, mine, debounced, page],
  );

  return (
    <TrainerPage>
      <PageHeader
        title="Academy library"
        subtitle="Articles, blogs and photos from the academy."
        actions={canWrite && <ButtonLink to={`${base}/content/new`}>New post</ButtonLink>}
      />

      <div className="tr-tabs" role="tablist" aria-label="Post type">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            className="tr-tab"
            aria-selected={tab === item.id}
            onClick={() => {
              setTab(item.id);
              setPage(1);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="tr-filters">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          label="Search posts"
        />
        {canWrite && (
          <label className="tr-checkbox">
            <input
              type="checkbox"
              checked={mine}
              onChange={(event) => {
                setMine(event.target.checked);
                setPage(1);
              }}
            />
            <span>My posts and drafts</span>
          </label>
        )}
      </div>

      <Loaded result={result}>
        {(data) =>
          data.items.length === 0 ? (
            <Empty
              title="Nothing published here yet"
              message={canWrite ? 'Write the first post for your academy.' : undefined}
            />
          ) : (
            <>
              <div className={tab === 'photo' ? 'gallery-grid' : 'tr-grid tr-grid--cards'}>
                {data.items.map((post) => (
                  <PostCard key={post.id} post={post} base={base} compact={tab === 'photo'} />
                ))}
              </div>
              <Pagination
                page={data.page}
                pages={data.pages}
                total={data.total}
                onChange={setPage}
                label="posts"
              />
            </>
          )
        }
      </Loaded>
    </TrainerPage>
  );
}

function PostCard({ post, base, compact }) {
  return (
    <Link
      to={`${base}/content/${post.id}`}
      className={`tr-card post-card ${compact ? 'is-photo' : ''}`}
    >
      {post.image_url && (
        <img src={apiUrl(post.image_url)} alt="" loading="lazy" className="post-card__image" />
      )}
      <span className="post-card__body">
        <strong>{post.title}</strong>
        {!compact && post.excerpt && <span className="tr-muted">{post.excerpt}</span>}
        <span className="tr-muted">
          {post.type === 'photo' ? 'Photo' : post.type === 'blog' ? 'Blog' : 'Article'} ·{' '}
          {post.author_name} · {formatDate(post.published_at ?? post.created_at)}
        </span>
        {post.status !== 'published' && <Status value={post.status} />}
      </span>
    </Link>
  );
}
