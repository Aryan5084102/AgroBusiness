import Link from 'next/link';
import { LoginForm } from '@/features/auth/LoginForm';
import { createTranslator, defaultLocale } from '@/lib/i18n';
import styles from './page.module.scss';

const t = createTranslator(defaultLocale);

export default function LandingPage() {
  return (
    <main className={styles.layout}>
      <section className={styles.brandPanel} aria-hidden="true">
        <div className={styles.brandInner}>
          <span className={styles.logo}>AgriFlow</span>
          <p className={styles.tagline}>{t('app.tagline')}</p>
        </div>
      </section>

      <section className={styles.formPanel}>
        <LoginForm />
        <Link href="/status" className={styles.statusLink}>
          {t('status.title')}
        </Link>
      </section>
    </main>
  );
}
