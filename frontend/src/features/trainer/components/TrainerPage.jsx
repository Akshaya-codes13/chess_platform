import '../trainer.css';
import { Toaster } from './Toast';

/** Root wrapper for every Trainer page: scoped styles plus the toast region. */
export default function TrainerPage({ children }) {
  return (
    <div className="tr-root">
      {children}
      <Toaster />
    </div>
  );
}
