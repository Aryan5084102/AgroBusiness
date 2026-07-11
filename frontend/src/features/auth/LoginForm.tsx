'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { createTranslator, defaultLocale } from '@/lib/i18n';
import { useLogin } from './useAuth';
import { loginSchema, type LoginInput } from './schema';
import styles from './LoginForm.module.scss';

const t = createTranslator(defaultLocale);

/**
 * Login form wired to the backend cookie-based auth. On success the session
 * cookie is set by the server and the user is routed to the dashboard.
 */
export function LoginForm() {
  const router = useRouter();
  const loginMutation = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({ defaultValues: { email: '', password: '' } });

  const onSubmit = async (values: LoginInput) => {
    setFormError(null);
    const parsed = loginSchema.safeParse(values);
    if (!parsed.success) return;
    try {
      await loginMutation.mutateAsync(parsed.data);
      router.push('/dashboard');
    } catch (err) {
      // Never surface raw backend errors; map to a friendly message.
      setFormError(
        err instanceof ApiError
          ? err.message
          : 'Unable to sign in right now. Please try again.',
      );
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <h1 className={styles.title}>{t('auth.signInCta')}</h1>

      <div className={styles.field}>
        <label htmlFor="email">{t('auth.email')}</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={Boolean(errors.email)}
          {...register('email', { required: true })}
        />
        {errors.email ? (
          <span role="alert" className={styles.error}>
            Email is required
          </span>
        ) : null}
      </div>

      <div className={styles.field}>
        <label htmlFor="password">{t('auth.password')}</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', { required: true })}
        />
        {errors.password ? (
          <span role="alert" className={styles.error}>
            Password is required
          </span>
        ) : null}
      </div>

      <Button type="submit" size="lg" isLoading={loginMutation.isPending}>
        {t('auth.signIn')}
      </Button>

      {formError ? (
        <p role="alert" className={styles.notice}>
          {formError}
        </p>
      ) : null}
    </form>
  );
}
