import { useEffect, useRef, useState } from 'react';
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
}

export const ToastContainer = () => {
  const [toasts, setToasts] = useState<ActiveToast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    const unsubscribe = subscribeToasts((toast) => {
      setToasts((prev) => [...prev, { ...toast, exiting: false }]);

      const dismissDelay = AUTO_DISMISS_MS[toast.variant] ?? 3500;
      const exitTimer = setTimeout(() => {
        setToasts((prev) => prev.map((t) => (t.id === toast.id ? { ...t, exiting: true } : t)));

        const removeTimer = setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== toast.id));
          timers.current.delete(toast.id);
        }, 200);
        timers.current.set(toast.id, removeTimer);
      }, dismissDelay);
      timers.current.set(toast.id, exitTimer);
    });

    const activeTimers = timers.current;
    return () => {
      unsubscribe();
      activeTimers.forEach((timer) => clearTimeout(timer));
      activeTimers.clear();
    };
  }, []);

  const handleDismiss = (id: string) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 200);
  };

  if (toasts.length === 0) return null;

  return createPortal(
    <div
      className="fixed top-20 right-4 z-[60] flex flex-col gap-2 w-[min(340px,calc(100vw-2rem))] pointer-events-none"
      aria-live="polite"
      aria-atomic="false"
    >
      {toasts.map((toast) => {
        const style = VARIANT_STYLES[toast.variant];
        const isEmphasis = toast.variant === 'levelup' || toast.variant === 'milestone';
        return (
          <div
            key={toast.id}
            role="status"
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
              className="text-on-surface-variant hover:text-on-surface shrink-0 cursor-pointer"
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
