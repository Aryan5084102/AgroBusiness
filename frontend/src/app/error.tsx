'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/Button';

// Route-level error boundary. Shows a friendly message; never leaks stack traces.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Client-side logging hook (wired to a telemetry sink in a later phase).
    console.error('Route error', error.digest ?? error.message);
  }, [error]);

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        textAlign: 'center',
      }}
    >
      <div>
        <h1 style={{ fontSize: 22 }}>Something went wrong</h1>
        <p style={{ color: 'var(--color-text-secondary)', margin: '12px 0 20px' }}>
          The page could not be displayed. You can try again.
        </p>
        <Button onClick={reset}>Try again</Button>
      </div>
    </main>
  );
}
