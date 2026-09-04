import { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAppContext } from '../../context/AppContext';

export const Navbar = () => {
  const location = useLocation();
  const { state, openAuthModal, logout, clearBuildInspiration } = useAppContext();
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isProfilePopoverOpen, setIsProfilePopoverOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const profilePopoverRef = useRef<HTMLDivElement>(null);
  const profileBtnRef = useRef<HTMLButtonElement>(null);

  const navLinks = [
    { name: 'Discover', path: '/' },
    { name: 'Build', path: '/build' },
    { name: 'My Games', path: '/dashboard' },
    { name: 'Profile', path: '/profile' },
  ];

  const secondaryNavLinks = [
    { name: 'Documentation', path: '/documentation', icon: 'description' },
    { name: 'API Access', path: '/api-access', icon: 'key' },
    { name: 'Community', path: '/community', icon: 'groups' },
  ];

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/' || location.pathname.startsWith('/discover');
    return location.pathname === path || location.pathname.startsWith(path);
  };

  // Close drawer and profile popover upon route change
  useEffect(() => {
    setIsMobileDrawerOpen(false);
    setIsProfilePopoverOpen(false);
  }, [location.pathname]);

  // Handle outside click and Escape key for profile popover
  useEffect(() => {
    if (!isProfilePopoverOpen) return;

    const handleMouseDown = (e: MouseEvent) => {
      if (
        profilePopoverRef.current &&
        !profilePopoverRef.current.contains(e.target as Node) &&
        profileBtnRef.current &&
        !profileBtnRef.current.contains(e.target as Node)
      ) {
        setIsProfilePopoverOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsProfilePopoverOpen(false);
      }
    };

    document.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isProfilePopoverOpen]);

  // Lock body scroll and handle Escape key when mobile drawer is open
  useEffect(() => {
    if (!isMobileDrawerOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsMobileDrawerOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMobileDrawerOpen]);

  return (
    <header className="glass-nav sticky top-0 z-40 w-full border-b border-primary/30 shadow-[0_0_10px_rgba(76,224,210,0.2)]">
      <div className="max-w-[1080px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3 sm:gap-4">
          <span className="material-symbols-outlined text-primary text-xl" aria-hidden="true">deployed_code</span>
          <Link to="/" className="font-display text-base md:text-lg text-primary tracking-tighter text-glow-cyan uppercase">
            GameForge AI
          </Link>
        </div>

        {/* Center Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-4 h-full" aria-label="Desktop primary navigation">
          {navLinks.map((link) => {
            const active = isActive(link.path);
            return (
              <Link
                key={link.name}
                to={link.path}
                onClick={link.path === '/build' ? clearBuildInspiration : undefined}
                aria-current={active ? 'page' : undefined}
                className={`relative h-full flex items-center font-mono text-xs uppercase tracking-wider transition-colors px-3 ${
                  active ? 'text-primary text-glow-cyan font-bold' : 'text-on-surface-variant hover:text-primary'
                }`}
              >
                {link.name}
                {/* Animated active indicator */}
                <div
                  className={`absolute bottom-0 left-0 w-full h-[2px] bg-primary transition-transform duration-300 origin-center ${
                    active ? 'scale-x-100 glow-cyan' : 'scale-x-0'
                  }`}
                />
              </Link>
            );
          })}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            to="/build"
            onClick={clearBuildInspiration}
            className="bg-secondary-container text-white font-mono text-[10px] sm:text-xs uppercase py-2 px-3 sm:px-4 glow-box-magenta flex items-center gap-1.5 sm:gap-2 btn-interactive glow-magenta energy-sweep"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true" style={{ fontVariationSettings: "'FILL' 1" }}>
              construction
            </span>
            <span className="hidden sm:inline">Build a Game</span>
          </Link>

          {state.authStatus === 'AUTHENTICATED' && state.user ? (
            <div className="relative">
              <button
                ref={profileBtnRef}
                type="button"
                onClick={() => setIsProfilePopoverOpen((prev) => !prev)}
                className="h-9 px-2.5 rounded-sm border border-outline-variant bg-surface-container flex items-center gap-2 text-primary icon-interactive hover:border-primary transition-colors font-mono text-xs cursor-pointer"
                title={`Logged in as ${state.user.username} (Level ${state.progress?.current_level || state.user.level || 1} ${state.progress?.creator_title || 'Creator'})`}
                aria-expanded={isProfilePopoverOpen}
                aria-haspopup="true"
              >
                {state.user.avatar_url ? (
                  <img
                    src={state.user.avatar_url}
                    alt={state.user.username}
                    className="w-6 h-6 rounded-full object-cover border border-primary/50"
                  />
                ) : (
                  <span className="material-symbols-outlined text-base" aria-hidden="true">account_circle</span>
                )}
                <span className="hidden md:inline font-bold">{state.user.username}</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-primary/15 text-primary border border-primary/40 font-mono font-bold tracking-tight">
                  LVL {state.progress?.current_level || state.user.level || 1}
                </span>
                <span className="material-symbols-outlined text-xs text-primary/70" aria-hidden="true">
                  {isProfilePopoverOpen ? 'expand_less' : 'expand_more'}
                </span>
              </button>

              {isProfilePopoverOpen && (
                <div
                  ref={profilePopoverRef}
                  className="absolute right-0 top-full mt-2 w-72 bg-surface-container-high border-2 border-primary shadow-[0_0_30px_rgba(76,224,210,0.25)] rounded-md p-3 z-50 animate-fadeIn font-mono text-xs space-y-3"
                  role="menu"
                  aria-label="Profile navigation menu"
                >
                  {/* User Summary Header */}
                  <div className="flex items-center gap-2.5 pb-2.5 border-b border-primary/20">
                    <div className="w-10 h-10 rounded-full border border-primary/60 bg-surface-container-highest flex items-center justify-center shrink-0 overflow-hidden">
                      {state.user.avatar_url ? (
                        <img src={state.user.avatar_url} alt={state.user.username} className="w-full h-full object-cover" />
                      ) : (
                        <span className="material-symbols-outlined text-primary text-xl">person</span>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-display text-xs text-primary truncate uppercase">{state.user.username}</div>
                      <div className="text-[10px] text-tertiary font-bold truncate">
                        Level {state.progress?.current_level || state.user.level || 1} • {state.progress?.creator_title || 'Novice Creator'}
                      </div>
                      <div className="text-[9px] text-on-surface-variant truncate">{state.user.email}</div>
                    </div>
                  </div>

                  {/* Level & XP Quick Bar */}
                  <div className="space-y-1 bg-surface-container-low p-2 rounded border border-outline-variant/30">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-on-surface-variant uppercase">XP Progress:</span>
                      <span className="text-tertiary font-bold">{state.progress?.total_xp || 0} XP</span>
                    </div>
                    <div className="w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-tertiary h-full transition-all duration-300 rounded-full"
                        style={{ width: `${Math.min(100, ((state.progress?.total_xp || 0) % 500) / 5)}%` }}
                      />
                    </div>
                  </div>

                  {/* Navigation Links */}
                  <div className="space-y-1 pt-1">
                    <Link
                      to="/profile"
                      onClick={() => setIsProfilePopoverOpen(false)}
                      className="w-full px-2.5 py-2 rounded hover:bg-primary/10 text-on-surface hover:text-primary flex items-center gap-2 transition-colors cursor-pointer"
                      role="menuitem"
                    >
                      <span className="material-symbols-outlined text-sm text-primary">person</span>
                      <span>View Full Profile</span>
                    </Link>

                    <Link
                      to="/profile"
                      onClick={() => {
                        setIsProfilePopoverOpen(false);
                      }}
                      className="w-full px-2.5 py-2 rounded hover:bg-primary/10 text-on-surface hover:text-primary flex items-center gap-2 transition-colors cursor-pointer"
                      role="menuitem"
                    >
                      <span className="material-symbols-outlined text-sm text-primary">manage_accounts</span>
                      <span>Account Settings</span>
                    </Link>

                    <Link
                      to="/dashboard"
                      onClick={() => setIsProfilePopoverOpen(false)}
                      className="w-full px-2.5 py-2 rounded hover:bg-primary/10 text-on-surface hover:text-primary flex items-center gap-2 transition-colors cursor-pointer"
                      role="menuitem"
                    >
                      <span className="material-symbols-outlined text-sm text-secondary">sports_esports</span>
                      <span>My Projects ({state.myGames.length})</span>
                    </Link>
                  </div>

                  {/* Sign Out Action */}
                  <div className="pt-2 border-t border-primary/20">
                    <button
                      type="button"
                      onClick={() => {
                        setIsProfilePopoverOpen(false);
                        logout();
                      }}
                      className="w-full px-2.5 py-2 rounded hover:bg-error/10 text-error flex items-center gap-2 transition-colors cursor-pointer text-xs"
                      role="menuitem"
                    >
                      <span className="material-symbols-outlined text-sm">logout</span>
                      <span>Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => openAuthModal('login')}
              className="h-9 px-3 rounded-sm border border-primary/50 bg-surface-container flex items-center gap-1.5 text-primary icon-interactive hover:border-primary hover:bg-primary/10 transition-colors font-mono text-xs cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm" aria-hidden="true">login</span>
              <span className="hidden sm:inline font-bold">Sign In</span>
            </button>
          )}

          {/* Mobile Menu Hamburger Trigger */}
          <button
            type="button"
            onClick={() => setIsMobileDrawerOpen((prev) => !prev)}
            className="md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center text-primary icon-interactive hover:bg-primary/10 rounded border border-primary/40 transition-colors cursor-pointer"
            aria-label="Toggle navigation drawer"
            aria-expanded={isMobileDrawerOpen}
          >
            <span className="material-symbols-outlined text-xl" aria-hidden="true">
              {isMobileDrawerOpen ? 'close' : 'menu'}
            </span>
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer Sheet */}
      {isMobileDrawerOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden bg-background/80 backdrop-blur-md flex justify-end modal-backdrop-enter"
          onClick={() => setIsMobileDrawerOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation menu"
        >
          <div
            ref={drawerRef}
            className="w-[280px] sm:w-[320px] h-full bg-surface border-l-2 border-primary shadow-[0_0_40px_rgba(76,224,210,0.25)] flex flex-col p-6 space-y-6 overflow-y-auto modal-enter"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Top Header */}
            <div className="flex items-center justify-between border-b border-primary/30 pb-4">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-lg" aria-hidden="true">deployed_code</span>
                <span className="font-display text-sm text-primary tracking-tight uppercase">GameForge</span>
              </div>
              <button
                type="button"
                onClick={() => setIsMobileDrawerOpen(false)}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center text-on-surface-variant hover:text-primary transition-colors cursor-pointer rounded focus:outline-none focus:ring-1 focus:ring-primary"
                aria-label="Close navigation drawer"
              >
                <span className="material-symbols-outlined text-lg" aria-hidden="true">close</span>
              </button>
            </div>

            {/* Primary Mobile Nav Links */}
            <nav className="space-y-1.5" aria-label="Mobile primary navigation">
              <div className="text-[10px] font-mono text-on-surface-variant/70 uppercase tracking-widest px-2 mb-2 font-bold">
                // CORE_NAVIGATION
              </div>
              {navLinks.map((link) => {
                const active = isActive(link.path);
                return (
                  <Link
                    key={link.name}
                    to={link.path}
                    onClick={link.path === '/build' ? clearBuildInspiration : undefined}
                    aria-current={active ? 'page' : undefined}
                    className={`flex items-center justify-between min-h-[44px] px-3.5 py-2.5 rounded font-mono text-xs uppercase tracking-wider transition-all ${
                      active
                        ? 'bg-primary/15 border border-primary text-primary font-bold shadow-[0_0_12px_rgba(76,224,210,0.3)]'
                        : 'text-on-surface hover:bg-surface-container hover:text-primary border border-transparent'
                    }`}
                  >
                    <span>{link.name}</span>
                    {active && <span className="material-symbols-outlined text-sm text-primary" aria-hidden="true">chevron_right</span>}
                  </Link>
                );
              })}
            </nav>

            {/* Secondary Navigation Links */}
            <div className="space-y-1.5 border-t border-primary/20 pt-4">
              <div className="text-[10px] font-mono text-on-surface-variant/70 uppercase tracking-widest px-2 mb-2 font-bold">
                // SYSTEM_LINKS
              </div>
              {secondaryNavLinks.map((link) => (
                <Link
                  key={link.name}
                  to={link.path}
                  className="flex items-center gap-2.5 min-h-[44px] px-3.5 py-2 rounded text-on-surface-variant hover:text-primary hover:bg-surface-container font-mono text-xs tracking-wide transition-colors"
                >
                  <span className="material-symbols-outlined text-base" aria-hidden="true">{link.icon}</span>
                  <span>{link.name}</span>
                </Link>
              ))}
            </div>

            {/* Auth / Profile Area in Drawer */}
            <div className="mt-auto border-t border-primary/20 pt-4">
              {state.authStatus === 'AUTHENTICATED' && state.user ? (
                <div className="p-3 bg-surface-container border border-primary/30 rounded flex items-center gap-3">
                  {state.user.avatar_url ? (
                    <img
                      src={state.user.avatar_url}
                      alt={state.user.username}
                      className="w-8 h-8 rounded-full object-cover border border-primary"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary flex items-center justify-center text-primary">
                      <span className="material-symbols-outlined text-sm">person</span>
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs text-white font-bold truncate">{state.user.username}</div>
                    <div className="text-[10px] font-mono text-primary">LVL {state.progress?.current_level || state.user.level || 1} {state.progress?.creator_title || 'Creator'}</div>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setIsMobileDrawerOpen(false);
                    openAuthModal('login');
                  }}
                  className="w-full min-h-[44px] py-2.5 px-4 bg-primary/20 border border-primary text-primary hover:bg-primary/30 font-mono text-xs uppercase font-bold rounded flex items-center justify-center gap-2 transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-sm">login</span>
                  <span>AUTHENTICATE</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

