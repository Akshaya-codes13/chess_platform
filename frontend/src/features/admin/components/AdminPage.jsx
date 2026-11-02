import '../../trainer/trainer.css';
import '../admin.css';
import { Toaster } from '../../trainer/components/Toast';

/**
 * Root wrapper for every Admin page. Admin reuses the Trainer module's
 * component kit, so it renders inside the same scoped `.tr-root`.
 */
export default function AdminPage({ children }) {
  return (
    <div className="tr-root ad-root">
      {children}
      <Toaster />
    </div>
  );
}
