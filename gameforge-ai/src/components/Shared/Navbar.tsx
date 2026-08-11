import { Link, useLocation } from 'react-router-dom';

export const Navbar = () => {
  const location = useLocation();

  const navLinks = [
    { name: 'Discover', path: '/' },
    { name: 'Build', path: '/build' },
    { name: 'My Games', path: '/dashboard' },
    { name: 'Profile', path: '/profile' }
  ];

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/' || location.pathname.startsWith('/discover');
    return location.pathname === path || location.pathname.startsWith(path);
  };

  return (
    <header className="glass-nav sticky top-0 z-40 w-full border-b border-primary/30 shadow-[0_0_10px_rgba(76,224,210,0.2)]">
      <div className="max-w-[1080px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-4">
          <span className="material-symbols-outlined text-primary text-xl">deployed_code</span>
          <Link to="/" className="font-display text-base md:text-lg text-primary tracking-tighter text-glow-cyan uppercase">
            GameForge AI
          </Link>
        </div>
        
        {/* Center Navigation */}
        <nav className="hidden md:flex items-center gap-4 h-full">
          {navLinks.map((link) => {
            const active = isActive(link.path);
            return (
              <Link
                key={link.name}
                to={link.path}
                className={`relative h-full flex items-center font-mono text-xs uppercase tracking-wider transition-colors px-3 ${
                  active ? 'text-primary text-glow-cyan' : 'text-on-surface-variant hover:text-primary'
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
        <div className="flex items-center gap-3">
          <Link to="/build" className="bg-secondary-container text-white font-mono text-[10px] uppercase py-2 px-4 glow-box-magenta flex items-center gap-2 btn-interactive glow-magenta energy-sweep">
            <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>construction</span>
            <span className="hidden md:inline">Build a Game</span>
          </Link>
          <Link to="/profile" className="w-8 h-8 rounded-sm border border-outline-variant bg-surface-container flex items-center justify-center text-primary icon-interactive hover:border-primary transition-colors">
            <span className="material-symbols-outlined text-sm">person</span>
          </Link>
        </div>
      </div>
    </header>
  );
};
