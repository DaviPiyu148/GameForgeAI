import { useEffect, useRef, useState, useCallback } from 'react';

interface UseModalDialogOptions {
  isOpen: boolean;
  onClose: () => void;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  closeDelayMs?: number;
}

interface UseModalDialogReturn {
  isClosing: boolean;
  handleClose: () => void;
  handleBackdropClick: (e: React.MouseEvent<HTMLElement>) => void;
  dialogRef: React.RefObject<HTMLDivElement | null>;
}

const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

export function useModalDialog({
  isOpen,
  onClose,
  initialFocusRef,
  closeDelayMs = 200,
}: UseModalDialogOptions): UseModalDialogReturn {
  const [isClosing, setIsClosing] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  const handleClose = useCallback(() => {
    if (isClosing) return;

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion || closeDelayMs <= 0) {
      onClose();
      return;
    }

    setIsClosing(true);
    const timer = setTimeout(() => {
      onClose();
      setIsClosing(false);
    }, closeDelayMs);

    return () => clearTimeout(timer);
  }, [isClosing, onClose, closeDelayMs]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLElement>) => {
      if (e.target === e.currentTarget && !isClosing) {
        handleClose();
      }
    },
    [isClosing, handleClose]
  );

  // Body scroll lock with scrollbar shift compensation
  useEffect(() => {
    if (!isOpen) {
      setIsClosing(false);
      return;
    }

    previousActiveElementRef.current = document.activeElement as HTMLElement | null;

    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
    const originalOverflow = document.body.style.overflow;
    const originalPaddingRight = document.body.style.paddingRight;

    document.body.style.overflow = 'hidden';
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }

    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.paddingRight = originalPaddingRight;
    };
  }, [isOpen]);

  // Initial focus and focus restoration
  useEffect(() => {
    if (!isOpen) return;

    const focusTimer = setTimeout(() => {
      if (initialFocusRef?.current) {
        initialFocusRef.current.focus();
      } else if (dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS);
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          dialogRef.current.focus();
        }
      }
    }, 50);

    return () => {
      clearTimeout(focusTimer);
      if (previousActiveElementRef.current && typeof previousActiveElementRef.current.focus === 'function') {
        previousActiveElementRef.current.focus();
      }
    };
  }, [isOpen, initialFocusRef]);

  // Escape key listener & Tab focus trap
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isClosing) {
        e.preventDefault();
        handleClose();
        return;
      }

      if (e.key === 'Tab' && dialogRef.current) {
        const focusable = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS)
        ).filter((el) => el.offsetParent !== null);

        if (focusable.length === 0) {
          e.preventDefault();
          return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isClosing, handleClose]);

  return {
    isClosing,
    handleClose,
    handleBackdropClick,
    dialogRef,
  };
}
