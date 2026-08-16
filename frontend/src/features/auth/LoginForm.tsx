'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { defaultRouteFor } from '@/components/layout/navItems';
import { ApiError } from '@/lib/api/client';
import { createTranslator, defaultLocale } from '@/lib/i18n';
import { DemoAccounts } from './DemoAccounts';
import { useLogin } from './useAuth';
import { loginSchema, type LoginInput } from './schema';
import styles from './LoginForm.module.scss';

const t = createTranslator(defaultLocale);

/**
 * Login form wired to the backend's cookie-based auth. On success the session
 * cookie is set by the server and the user is routed to the first page their
 * role can actually use — a technician lands in the workshop, not on a
 * dashboard they have no permission to read.
 */
export function LoginForm() {
  const router = useRouter();
  const loginMutation = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<LoginInput>({ defaultValues: { email: '', password: '' } });

  const doLogin = async (email: string, password: string) => {
    setFormError(null);
    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      setFormError('Enter a valid email address and your password.');
      return;
    }
    try {
      const result = await loginMutation.mutateAsync(parsed.data);
      const permissions = new Set(result.user.permissions);
      const can = (code: string) => result.user.is_owner || permissions.has(code);
      router.push(defaultRouteFor(can));
    } catch (err) {
      // Never surface raw backend errors; map to a friendly message.
      setFormError(
        err instanceof ApiError
          ? err.message
          : 'Unable to sign in right now. Please try again.',
      );
    }
  };

  const onSubmit = (values: LoginInput) => doLogin(values.email, values.password);

  const onPickDemo = (email: string, password: string) => {
    // Reflect the choice in the inputs, then sign in.
    setValue('email', email);
    setValue('password', password);
    void doLogin(email, password);
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <div className={styles.heading}>
        <h2 className={styles.title}>{t('auth.signInCta')}</h2>
        <p className={styles.subtitle}>
          Use your work email. Your role decides what you see next.
        </p>
      </div>

      <Input
        label={t('auth.email')}
        type="email"
        autoComplete="email"
        error={errors.email ? 'Email is required' : undefined}
        {...register('email', { required: true })}
      />

      <Input
        label={t('auth.password')}
        type="password"
        autoComplete="current-password"
        error={errors.password ? 'Password is required' : undefined}
        {...register('password', { required: true })}
      />

      <Button type="submit" size="lg" isLoading={loginMutation.isPending}>
        {t('auth.signIn')}
      </Button>

      {formError ? (
        <p role="alert" className={styles.notice}>
          {formError}
        </p>
      ) : null}

      <DemoAccounts onPick={onPickDemo} disabled={loginMutation.isPending} />
    </form>
  );
}
