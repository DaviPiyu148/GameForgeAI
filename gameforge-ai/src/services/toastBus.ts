// Lightweight, framework-agnostic pub/sub so any part of the app (including
// AppContext, which sits above the component tree) can raise a transient toast
// without threading toast state through the global AppState/reducer.
export type ToastVariant = 'info' | 'success' | 'xp' | 'levelup' | 'milestone' | 'error';

export interface ToastMessage {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

type Listener = (toast: ToastMessage) => void;

const listeners = new Set<Listener>();

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function pushToast(toast: Omit<ToastMessage, 'id'>): void {
  const message: ToastMessage = {
    ...toast,
    id: `toast_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
  };
  listeners.forEach((listener) => listener(message));
}
