import Link from 'next/link';

export default function NotFound() {
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
        <h1 style={{ fontSize: 22 }}>Page not found</h1>
        <p style={{ color: 'var(--color-text-secondary)', margin: '12px 0 20px' }}>
          The page you are looking for does not exist.
        </p>
        <Link href="/" style={{ color: 'var(--color-action-green)', fontWeight: 600 }}>
          Return home
        </Link>
      </div>
    </main>
  );
}
