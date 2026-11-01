import { useEffect, useState } from 'react';
import { api } from './api/client';

export default function App() {
  const [status, setStatus] = useState('checking...');

  useEffect(() => {
    api('/health/db')
      .then(() => setStatus('API and database connected'))
      .catch(() => setStatus('API not reachable'));
  }, []);

  return (
    <main style={{ fontFamily: 'system-ui', padding: 32 }}>
      <h1>Chess Academy</h1>
      <p>{status}</p>
    </main>
  );
}
