import Button from './Button';
import Spinner from './Spinner';

/** Renders a spinner or an error with a retry button; renders nothing otherwise. */
export default function LoadState({ loading, error, onRetry }) {
  if (loading) return <Spinner />;
  if (!error) return null;

  const message =
    error.message ||
    (error.status === 404
      ? 'This page could not be found, or you do not have access to it.'
      : 'Something went wrong while loading this page.');

  return (
    <div className="load-error" role="alert">
      <p>{message}</p>
      {onRetry && error.status !== 404 && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
