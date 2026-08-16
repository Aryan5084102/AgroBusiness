'use client';

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import styles from './Field.module.scss';

interface FieldShellProps {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  /** Renders the label visually hidden — for toolbars where context is obvious. */
  hideLabel?: boolean;
}

/** Label + control + hint/error, wired with the right aria-* attributes. */
function FieldShell({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
  hideLabel,
}: FieldShellProps) {
  return (
    <div className={styles.field}>
      <label htmlFor={htmlFor} className={hideLabel ? styles.srOnly : styles.label}>
        {label}
        {required ? (
          <span className={styles.required} aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? (
        <span role="alert" className={styles.error}>
          {error}
        </span>
      ) : hint ? (
        <span className={styles.hint}>{hint}</span>
      ) : null}
    </div>
  );
}

export interface InputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'id' | 'prefix'
> {
  label: string;
  hint?: string;
  error?: string;
  hideLabel?: boolean;
  /** Rendered inside the control, before the text (e.g. a ₹ or a search icon). */
  prefix?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, hideLabel, prefix, required, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <FieldShell
      label={label}
      htmlFor={id}
      hint={hint}
      error={error}
      required={required}
      hideLabel={hideLabel}
    >
      <span className={`${styles.control} ${error ? styles.invalid : ''}`}>
        {prefix ? <span className={styles.prefix}>{prefix}</span> : null}
        <input
          id={id}
          ref={ref}
          required={required}
          aria-invalid={error ? true : undefined}
          className={[styles.input, className].filter(Boolean).join(' ')}
          {...rest}
        />
      </span>
    </FieldShell>
  );
});

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  label: string;
  hint?: string;
  error?: string;
  hideLabel?: boolean;
  children: ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, hideLabel, required, children, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <FieldShell
      label={label}
      htmlFor={id}
      hint={hint}
      error={error}
      required={required}
      hideLabel={hideLabel}
    >
      <span className={`${styles.control} ${error ? styles.invalid : ''}`}>
        <select
          id={id}
          ref={ref}
          required={required}
          aria-invalid={error ? true : undefined}
          className={[styles.input, styles.select, className].filter(Boolean).join(' ')}
          {...rest}
        >
          {children}
        </select>
      </span>
    </FieldShell>
  );
});

export interface TextAreaProps extends Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>,
  'id'
> {
  label: string;
  hint?: string;
  error?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, hint, error, required, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <FieldShell label={label} htmlFor={id} hint={hint} error={error} required={required}>
      <span className={`${styles.control} ${error ? styles.invalid : ''}`}>
        <textarea
          id={id}
          ref={ref}
          required={required}
          aria-invalid={error ? true : undefined}
          className={[styles.input, styles.textarea, className].filter(Boolean).join(' ')}
          {...rest}
        />
      </span>
    </FieldShell>
  );
});

/** Row of fields that wraps on narrow screens. */
export function FieldRow({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}
