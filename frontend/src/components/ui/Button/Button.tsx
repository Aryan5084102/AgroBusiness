import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Icon, type IconName } from '@/components/ui/Icon/Icon';
import styles from './Button.module.scss';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'subtle';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: IconName;
  /** Renders icon-only; `aria-label` becomes required for the accessible name. */
  iconOnly?: boolean;
  children?: ReactNode;
}

/**
 * Accessible button primitive. Handles loading (aria-busy + disabled), an
 * optional leading icon, and variant/size styling via CSS-module classes.
 * Business components compose this rather than styling native buttons ad hoc.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    isLoading = false,
    icon,
    iconOnly = false,
    disabled,
    children,
    className,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      className={[
        styles.button,
        styles[variant],
        styles[size],
        iconOnly ? styles.iconOnly : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      {...rest}
    >
      {isLoading ? (
        <span className={styles.spinner} aria-hidden="true" />
      ) : icon ? (
        <Icon name={icon} size={size === 'sm' ? 15 : 16} />
      ) : null}
      {iconOnly ? null : <span>{children}</span>}
    </button>
  );
});
