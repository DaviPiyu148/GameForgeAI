import { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { subscribeToasts, type ToastMessage } from '../../services/toastBus';

const AUTO_DISMISS_MS: Record<ToastMessage['variant'], number> = {
  info: 3500,
  success: 3500,
  xp: 3000,
  levelup: 4500,
  milestone: 4500,
  error: 5000,
};

const VARIANT_STYLES: Record<
  ToastMessage['variant'],
  { icon: string; border: string; glow: string; iconColor: string }
> = {
  info: { icon: 'info', border: 'border-outline-variant', glow: '', iconColor: 'text-on-surface-variant' },
  success: { icon: 'check_circle', border: 'border-primary', glow: 'glow-box-cyan', iconColor: 'text-primary' },
  xp: { icon: 'bolt', border: 'border-primary', glow: 'glow-box-cyan', iconColor: 'text-primary' },
  levelup: { icon: 'military_tech', border: 'border-tertiary', glow: 'glow-box-amber', iconColor: 'text-tertiary' },
  milestone: { icon: 'emoji_events', border: 'border-secondary', glow: 'glow-box-magenta', iconColor: 'text-secondary' },
  error: { icon: 'error', border: 'border-error', glow: 'glow-error', iconColor: 'text-error' },
};

interface ActiveToast extends ToastMessage {
  exiting: boolean;
  remainingMs: number;
  startedAt: number;
}

export const ToastContainer = () => {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const isPaused = useRef(false);

  const startDismissTimer = useCallback((id: string, delay: number) => {
    const exitTimer = setTimeout(() => {
      setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));

      const removeTimer = setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        timers.current.delete(id);
      }, 200);
      timers.current.set(id, removeTimer);
    }, delay);

    timers.current.set(id, exitTimer);
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeToasts((toast) => {
      const dismissDelay = AUTO_DISMISS_MS[toast.variant] ?? 3500;
      const newToast: ActiveToast = {
        ...toast,
        exiting: false,
        remainingMs: dismissDelay,
        startedAt: Date.now(),
      };

      setToasts((prev) => [...prev, newToast]);

      if (!isPaused.current) {
        startDismissTimer(toast.id, dismissDelay);
      }
    });

    const activeTimers = timers.current;
    return () => {
      unsubscribe();
      activeTimers.forEach((timer) => clearTimeout(timer));
      activeTimers.clear();
    };
  }, [startDismissTimer]);

  const handleMouseEnter = () => {
    isPaused.current = true;
    // Clear active timeouts and record remaining time
    const now = Date.now();
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current.clear();

    setToasts((prev) =>
      prev.map((t) => {
        const elapsed = now - t.startedAt;
        const remaining = Math.max(1000, t.remainingMs - elapsed);
        return { ...t, remainingMs: remaining };
      })
    );
  };

  const handleMouseLeave = () => {
    isPaused.current = false;
    const now = Date.now();
    setToasts((prev) =>
      prev.map((t) => {
        const updated = { ...t, startedAt: now };
        startDismissTimer(t.id, t.remainingMs);
        return updated;
      })
    );
  };

  const handleDismiss = (id: string) => {
    const existing = timers.current.get(id);
    if (existing) clearTimeout(existing);

    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      timers.current.delete(id);
    }, 200);
  };

  if (toasts.length === 0) return null;

  return createPortal(
    <div
      className="fixed top-4 right-4 sm:top-20 sm:right-6 z-[60] flex flex-col gap-2 w-[min(380px,calc(100vw-2rem))] pointer-events-none"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
    >
      {toasts.map((toast) => {
        const style = VARIANT_STYLES[toast.variant];
        const isEmphasis = toast.variant === 'levelup' || toast.variant === 'milestone';
        const isError = toast.variant === 'error';
        return (
          <div
            key={toast.id}
            role={isError ? 'alert' : 'status'}
            aria-live={isError ? 'assertive' : 'polite'}
            className={`pointer-events-auto bg-surface border ${style.border} ${style.glow} rounded-sm shadow-2xl px-3.5 py-3 flex items-start gap-2.5 ${
              toast.exiting ? 'toast-exit' : isEmphasis ? 'toast-enter-emphasis' : 'toast-enter'
            }`}
          >
            <span className={`material-symbols-outlined text-lg shrink-0 ${style.iconColor}`} aria-hidden="true">
              {style.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className={`font-mono text-xs font-bold uppercase tracking-wide ${style.iconColor}`}>
                {toast.title}
              </div>
              {toast.description && (
                <div className="font-mono text-[11px] text-on-surface-variant mt-0.5 leading-snug">
                  {toast.description}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => handleDismiss(toast.id)}
              className="text-on-surface-variant hover:text-on-surface shrink-0 cursor-pointer min-w-[28px] min-h-[28px] flex items-center justify-center rounded"
              aria-label="Dismiss notification"
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        );
      })}
    </div>,
    document.body
  );
};

