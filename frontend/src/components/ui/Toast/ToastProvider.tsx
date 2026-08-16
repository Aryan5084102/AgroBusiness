'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Icon, type IconName } from '@/components/ui/Icon/Icon';
import styles from './Toast.module.scss';

export type ToastTone = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
  detail?: string;
}

interface ToastApi {
  success: (message: string, detail?: string) => void;
  error: (message: string, detail?: string) => void;
  info: (message: string, detail?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const ICONS: Record<ToastTone, IconName> = {
  success: 'check',
  error: 'alert',
  info: 'info',
};

// Errors linger longer — they usually need reading, not just noticing.
const DURATIONS: Record<ToastTone, number> = {
  success: 3500,
  info: 4000,
  error: 6000,
};

let nextId = 0;

/**
 * App-wide toast notifications. Screens call `toast.success(...)` after a
 * mutation instead of rendering their own inline status paragraphs, so feedback
 * is consistent and never shifts the layout.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (tone: ToastTone, message: string, detail?: string) => {
      const id = ++nextId;
      setToasts((prev) => [...prev, { id, tone, message, detail }]);
      setTimeout(() => dismiss(id), DURATIONS[tone]);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message, detail) => push('success', message, detail),
      error: (message, detail) => push('error', message, detail),
      info: (message, detail) => push('info', message, detail),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.viewport} role="region" aria-label="Notifications">
        {toasts.map((toast) => (
          <output
            key={toast.id}
            className={`${styles.toast} ${styles[toast.tone]}`}
            aria-live={toast.tone === 'error' ? 'assertive' : 'polite'}
          >
            <Icon name={ICONS[toast.tone]} size={17} />
            <span className={styles.text}>
              <span className={styles.message}>{toast.message}</span>
              {toast.detail ? (
                <span className={styles.detail}>{toast.detail}</span>
              ) : null}
            </span>
            <button
              type="button"
              className={styles.dismiss}
              aria-label="Dismiss notification"
              onClick={() => dismiss(toast.id)}
            >
              <Icon name="close" size={14} />
            </button>
          </output>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (context === null) {
    throw new Error('useToast must be used inside <ToastProvider>.');
  }
  return context;
}
