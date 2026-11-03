import { useRef, useState } from 'react';
import { apiUrl } from '../../api/client';
import { errorMessage, fieldErrors } from '../../features/trainer/api';
import ConfirmDialog from '../../features/trainer/components/ConfirmDialog';
import { SelectField, TextArea, TextField } from '../../features/trainer/components/Field';
import TrainerPage from '../../features/trainer/components/TrainerPage';
import { toast } from '../../features/trainer/components/toastStore';
import { Button, Loaded, PageHeader, Section, Status } from '../../features/trainer/components/ui';
import { useLoader } from '../../features/trainer/hooks';
import { sharedApi } from '../../features/shared/api';
import { navigate, useRoute } from '../../routes/router';
import { usePortalBase } from './base';

const TYPES = [
  { value: 'article', label: 'Article' },
  { value: 'blog', label: 'Blog post' },
  { value: 'photo', label: 'Gallery photo' },
];

export default function PostEditorPage() {
  const base = usePortalBase();
  const { params } = useRoute();
  const editing = Boolean(params.postId);
  const result = useLoader(
    () => (editing ? sharedApi.post(params.postId) : Promise.resolve(null)),
    [params.postId],
  );
  const ready = editing ? result : { ...result, data: result.loading ? null : {} };

  return (
    <TrainerPage>
      <PageHeader
        back={
          editing
            ? { to: `${base}/content/${params.postId}`, label: 'Post' }
            : { to: `${base}/content`, label: 'Academy library' }
        }
        title={editing ? 'Edit post' : 'New post'}
        subtitle="Posts start as drafts. Publishing makes them visible to everyone in the academy."
      />
      <Loaded result={ready}>
        {(post) => <PostForm post={editing ? post : null} base={base} onSaved={result.reload} />}
      </Loaded>
    </TrainerPage>
  );
}

function PostForm({ post, base, onSaved }) {
  const [form, setForm] = useState({
    title: post?.title ?? '',
    type: post?.type ?? 'article',
    content: post?.content ?? '',
    image_url: post?.image_url ?? null,
  });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const fileRef = useRef(null);

  async function uploadImage(file) {
    if (!file) return;
    setBusy('upload');
    try {
      const uploaded = await sharedApi.uploadImage(file);
      setForm((current) => ({ ...current, image_url: uploaded.url }));
      toast.success('Image uploaded.');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function save(event) {
    event.preventDefault();
    setBusy('save');
    setErrors({});
    const body = {
      title: form.title.trim(),
      type: form.type,
      content: form.content.trim() || null,
      image_url: form.image_url,
    };
    try {
      const saved = post
        ? await sharedApi.updatePost(post.id, body)
        : await sharedApi.createPost(body);
      toast.success(post ? 'Post saved.' : 'Draft created.');
      if (post) onSaved();
      else navigate(`${base}/content/${saved.id}/edit`, { replace: true });
    } catch (error) {
      setErrors(fieldErrors(error));
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function act(action) {
    setBusy(action);
    try {
      await sharedApi.postAction(post.id, action);
      toast.success(
        { publish: 'Published.', unpublish: 'Moved back to drafts.', archive: 'Archived.' }[action],
      );
      onSaved();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy('delete');
    try {
      await sharedApi.deletePost(post.id);
      toast.success('Post deleted.');
      navigate(`${base}/content`, { replace: true });
    } catch (error) {
      toast.error(errorMessage(error));
      setBusy(null);
      setConfirmDelete(false);
    }
  }

  return (
    <div className="tr-stack">
      {post && (
        <Section title="Publishing" actions={<Status value={post.status} />}>
          <div className="tr-page-actions">
            {post.status !== 'published' && (
              <Button onClick={() => act('publish')} disabled={Boolean(busy)}>
                Publish
              </Button>
            )}
            {post.status === 'published' && (
              <Button variant="secondary" onClick={() => act('unpublish')} disabled={Boolean(busy)}>
                Unpublish
              </Button>
            )}
            {post.status !== 'archived' && (
              <Button variant="secondary" onClick={() => act('archive')} disabled={Boolean(busy)}>
                Archive
              </Button>
            )}
            {post.status !== 'published' && (
              <Button
                variant="danger"
                onClick={() => setConfirmDelete(true)}
                disabled={Boolean(busy)}
              >
                Delete
              </Button>
            )}
          </div>
        </Section>
      )}

      <Section title="Content">
        <form className="tr-form" onSubmit={save}>
          <TextField
            label="Title"
            required
            maxLength={200}
            value={form.title}
            onChange={(title) => setForm({ ...form, title })}
            error={errors.title}
          />
          <SelectField
            label="Type"
            value={form.type}
            onChange={(type) => setForm({ ...form, type })}
            options={TYPES}
          />
          <TextArea
            label={form.type === 'photo' ? 'Caption' : 'Text'}
            rows={form.type === 'photo' ? 3 : 14}
            value={form.content}
            onChange={(content) => setForm({ ...form, content })}
            hint="Plain text. Leave a blank line between paragraphs."
            error={errors.content}
          />

          <div className="tr-field">
            <label className="tr-field__label" htmlFor="post-image">
              Image {form.type === 'photo' ? '(required)' : '(optional)'}
            </label>
            {form.image_url && (
              <div className="post-image-preview">
                <img src={apiUrl(form.image_url)} alt="Selected" />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setForm({ ...form, image_url: null })}
                >
                  Remove image
                </Button>
              </div>
            )}
            <input
              id="post-image"
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              onChange={(event) => uploadImage(event.target.files?.[0])}
              disabled={busy === 'upload'}
            />
            <p className="tr-field__hint">PNG, JPEG, WebP or GIF, up to 5 MB.</p>
            {errors.image_url && <p className="tr-field__error">{errors.image_url}</p>}
          </div>

          <div>
            <Button type="submit" disabled={Boolean(busy) || form.title.trim().length < 3}>
              {busy === 'save' ? 'Saving…' : post ? 'Save changes' : 'Create draft'}
            </Button>
          </div>
        </form>
      </Section>

      {post && (
        <ConfirmDialog
          open={confirmDelete}
          title="Delete this post?"
          message="The post is removed for good. Published posts must be unpublished first."
          confirmLabel="Delete post"
          tone="danger"
          busy={busy === 'delete'}
          onConfirm={remove}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}
