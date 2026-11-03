import { apiUrl } from '../../api/client';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { ButtonLink, Loaded, PageHeader, Status } from '../../features/trainer/components/ui';
import { formatDate } from '../../features/trainer/format';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { useRoute } from '../../routes/router';
import { usePortalBase } from './base';

export default function PostPage() {
  const base = usePortalBase();
  const { params } = useRoute();
  const result = useLoader(() => sharedApi.post(params.postId), [params.postId]);

  return (
    <TrainerPage>
      <Loaded result={result}>
        {(post) => (
          <article className="post-article">
            <PageHeader
              back={{ to: `${base}/content`, label: 'Academy library' }}
              title={post.title}
              subtitle={`${post.author_name} · ${formatDate(post.published_at ?? post.created_at)}`}
              actions={
                <>
                  {post.status !== 'published' && <Status value={post.status} />}
                  {post.can_edit && (
                    <ButtonLink to={`${base}/content/${post.id}/edit`} variant="secondary">
                      Edit
                    </ButtonLink>
                  )}
                </>
              }
            />
            {post.image_url && (
              <img className="post-article__image" src={apiUrl(post.image_url)} alt={post.title} />
            )}
            {/* Plain text: paragraphs split on blank lines, never rendered as HTML. */}
            <div className="post-article__body">
              {(post.content ?? '')
                .split(/\n{2,}/)
                .filter((paragraph) => paragraph.trim())
                .map((paragraph, index) => (
                  <p key={index}>{paragraph}</p>
                ))}
            </div>
          </article>
        )}
      </Loaded>
    </TrainerPage>
  );
}
