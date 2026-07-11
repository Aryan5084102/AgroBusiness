import { forwardRef, type ButtonHTMLAttributes } from 'react';
import styles from './Button.module.scss';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

/**
 * Accessible button primitive. Handles loading (aria-busy + disabled) and
 * variant/size styling via CSS-module classes. Business components compose this
 * rather than styling native buttons ad hoc.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', isLoading = false, disabled, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={`${styles.button} ${styles[variant]} ${styles[size]}`}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      {...rest}
    >
      {isLoading ? <span className={styles.spinner} aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  );
});
