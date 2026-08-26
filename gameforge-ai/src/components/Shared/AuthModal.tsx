import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useAppContext } from '../../context/AppContext';

export const AuthModal = () => {
  const { state, closeAuthModal, login, register } = useAppContext();
  const [mode, setMode] = useState<'login' | 'register'>(state.authModalMode || 'login');
  
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (state.authModalMode) {
      setMode(state.authModalMode);
    }
    setError(null);
  }, [state.authModalMode, state.isAuthModalOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state.isAuthModalOpen) {
        closeAuthModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state.isAuthModalOpen, closeAuthModal]);

  if (!state.isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (mode === 'login') {
        await login({ email: email.trim(), password });
      } else {
        if (!username.trim()) {
          setError('Please enter a username.');
          setIsSubmitting(false);
          return;
        }
        if (password.length < 8) {
          setError('Password must be at least 8 characters long.');
          setIsSubmitting(false);
          return;
        }
        await register({ email: email.trim(), username: username.trim(), password });
      }
    } catch (err: unknown) {
      const apiErr = err as { message?: string; code?: string };
      setError(apiErr.message || 'Authentication failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm modal-backdrop-enter"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeAuthModal();
      }}
    >
      <div
        className="w-full max-w-md max-h-[90vh] overflow-y-auto bg-surface border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] flex flex-col rounded-sm modal-enter relative z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Terminal Header */}
        <div className="bg-terminal-header border-b border-primary/30 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-base">lock</span>
            <span className="font-mono text-xs text-primary uppercase tracking-wider font-bold">
              SYS_AUTH // {mode === 'login' ? 'USER_LOGIN' : 'NEW_IDENTITY'}
            </span>
          </div>
          <button
            onClick={closeAuthModal}
            className="text-on-surface-variant hover:text-primary transition-colors cursor-pointer"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        <div className="p-6 bg-terminal-bg space-y-4">
          {/* Reason Alert (if triggered by action) */}
          {state.authModalReason && (
            <div className="p-3 bg-secondary-container/20 border border-secondary/40 font-mono text-xs text-secondary-soft flex items-start gap-2">
              <span className="material-symbols-outlined text-sm shrink-0">info</span>
              <span>{state.authModalReason}</span>
            </div>
          )}

          {/* Mode Switcher Tabs */}
          <div className="grid grid-cols-2 gap-2 border-b border-primary/20 pb-2">
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setError(null);
              }}
              className={`py-2 font-mono text-xs uppercase tracking-wider transition-colors cursor-pointer ${
                mode === 'login'
                  ? 'bg-primary text-on-primary font-bold shadow-[0_0_10px_rgba(76,224,210,0.3)]'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-primary'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setError(null);
              }}
              className={`py-2 font-mono text-xs uppercase tracking-wider transition-colors cursor-pointer ${
                mode === 'register'
                  ? 'bg-primary text-on-primary font-bold shadow-[0_0_10px_rgba(76,224,210,0.3)]'
                  : 'bg-surface-container-low text-on-surface-variant hover:text-primary'
              }`}
            >
              Register
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-error/10 border border-error text-error font-mono text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-sm shrink-0">error</span>
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block font-mono text-[10px] text-on-surface-variant mb-1 uppercase">
                  Username
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. CyberArchitect"
                  className="w-full bg-surface-container border border-primary/40 focus:border-primary text-primary font-mono text-xs p-2.5 outline-none"
                  disabled={isSubmitting}
                />
              </div>
            )}

            <div>
              <label className="block font-mono text-[10px] text-on-surface-variant mb-1 uppercase">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full bg-surface-container border border-primary/40 focus:border-primary text-primary font-mono text-xs p-2.5 outline-none"
                disabled={isSubmitting}
              />
            </div>

            <div>
              <label className="block font-mono text-[10px] text-on-surface-variant mb-1 uppercase">
                Password {mode === 'register' && <span className="text-on-surface-variant/70">(min 8 characters)</span>}
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-surface-container border border-primary/40 focus:border-primary text-primary font-mono text-xs p-2.5 outline-none"
                disabled={isSubmitting}
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={`w-full py-3 bg-secondary-container text-white font-mono text-xs uppercase tracking-wider flex items-center justify-center gap-2 btn-interactive energy-sweep glow-magenta cursor-pointer ${
                isSubmitting ? 'opacity-50 cursor-wait' : ''
              }`}
            >
              <span className={`material-symbols-outlined text-sm inline-block ${isSubmitting ? 'animate-spin' : ''}`}>
                {isSubmitting ? 'sync' : mode === 'login' ? 'login' : 'how_to_reg'}
              </span>
              <span>{isSubmitting ? 'Verifying...' : mode === 'login' ? 'Authenticate' : 'Create Account'}</span>
            </button>
          </form>

          <div className="text-center pt-2">
            <p className="font-mono text-[10px] text-on-surface-variant/70">
              {mode === 'login' ? "Don't have an account?" : 'Already registered?'}{' '}
              <button
                type="button"
                onClick={() => {
                  setMode(mode === 'login' ? 'register' : 'login');
                  setError(null);
                }}
                className="text-primary hover:underline font-bold cursor-pointer"
              >
                {mode === 'login' ? 'Register here' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
