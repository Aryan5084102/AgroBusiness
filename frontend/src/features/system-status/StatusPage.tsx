'use client';

import { Button } from '@/components/ui/Button';
import { createTranslator, defaultLocale } from '@/lib/i18n';
import { useHealth } from './useHealth';
import styles from './StatusPage.module.scss';

const t = createTranslator(defaultLocale);

// Frontend system-status page. Polls the backend aggregate health endpoint and
// renders each component with an icon + text + colour (never colour alone).
export function StatusPage() {
  const { data, isLoading, isError, refetch, isFetching } = useHealth();

  let headline = t('status.checking');
  let tone: 'neutral' | 'ok' | 'warn' | 'error' = 'neutral';
  if (isError) {
    headline = t('status.unreachable');
    tone = 'error';
  } else if (data) {
    headline = data.status === 'ok' ? t('status.healthy') : t('status.degraded');
    tone = data.status === 'ok' ? 'ok' : 'warn';
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1>{t('status.title')}</h1>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          isLoading={isFetching}
        >
          {t('common.retry')}
        </Button>
      </header>

      <div className={`${styles.banner} ${styles[tone]}`} role="status">
        <span className={styles.dot} aria-hidden="true" />
        <span>{headline}</span>
      </div>

      {data ? (
        <dl className={styles.meta}>
          <div>
            <dt>Environment</dt>
            <dd>{data.environment}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd className="tabular-nums">{data.version}</dd>
          </div>
        </dl>
      ) : null}

      <ul role="list" className={styles.components}>
        {(data?.components ?? []).map((component) => (
          <li key={component.name} className={styles.component}>
            <span
              className={`${styles.pill} ${
                component.status === 'up' ? styles.ok : styles.error
              }`}
            >
              {component.status === 'up' ? '● up' : '▲ down'}
            </span>
            <span className={styles.componentName}>{component.name}</span>
            {component.detail ? (
              <span className={styles.detail}>{component.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>

      {isLoading ? <p className={styles.loading}>{t('status.checking')}</p> : null}
    </main>
  );
}
