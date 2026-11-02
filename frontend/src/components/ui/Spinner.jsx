export default function Spinner({ label = 'Loading' }) {
  return (
    <div className="spinner" role="status">
      <span className="spinner-mark" aria-hidden="true" />
      <span className="visually-hidden">{label}</span>
    </div>
  );
}
