import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';
import { LoginForm } from '@/features/auth/LoginForm';
import { createTranslator, defaultLocale } from '@/lib/i18n';
import styles from './page.module.scss';

const t = createTranslator(defaultLocale);

const POINTS = [
  'One counter for retail billing and dealer orders',
  'Stock, batches and expiry tracked to the last bag',
  'Credit limits, collections and books that always balance',
] as const;

export default function LandingPage() {
  return (
    <main className={styles.layout}>
      <section className={styles.brandPanel}>
        <div className={styles.brandInner}>
          <span className={styles.logo}>
            <span className={styles.logoMark} aria-hidden="true">
              <Icon name="products" size={20} />
            </span>
            AgriFlow
          </span>
          <h1 className={styles.headline}>Run the whole shop from one screen.</h1>
          <p className={styles.tagline}>{t('app.tagline')}</p>
          <ul className={styles.points}>
            {POINTS.map((point) => (
              <li key={point} className={styles.point}>
                <span className={styles.pointIcon} aria-hidden="true">
                  <Icon name="check" size={14} />
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
        <p className={styles.brandFooter}>
          Every action is permission-checked and written to an audit trail.
        </p>
      </section>

      <section className={styles.formPanel}>
        <span className={styles.mobileBrand}>
          <Icon name="products" size={20} />
          AgriFlow
        </span>
        <LoginForm />
        <Link href="/status" className={styles.statusLink}>
          {t('status.title')}
        </Link>
      </section>
    </main>
  );
}
