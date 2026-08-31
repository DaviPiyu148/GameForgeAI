import React from 'react';
import { Link } from 'react-router-dom';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-surface-container-lowest w-full py-8 mt-auto border-t border-outline-variant z-10 relative">
      <div className="max-w-[1080px] mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="font-mono text-[10px] text-primary uppercase tracking-widest">
          © 2026 GAMEFORGE_AI // CORE_V1.0.2
        </div>
        <div className="flex flex-wrap justify-center gap-4">
          <Link
            to="/documentation"
            className="font-mono text-[10px] text-on-surface-variant hover:text-primary transition-colors uppercase"
          >
            Documentation
          </Link>
          <Link
            to="/api-access"
            className="font-mono text-[10px] text-on-surface-variant hover:text-primary transition-colors uppercase"
          >
            API Access
          </Link>
          <Link
            to="/community"
            className="font-mono text-[10px] text-on-surface-variant hover:text-primary transition-colors uppercase"
          >
            Community
          </Link>
          <Link
            to="/support"
            className="font-mono text-[10px] text-on-surface-variant hover:text-primary transition-colors uppercase"
          >
            Support
          </Link>
          <Link
            to="/privacy"
            className="font-mono text-[10px] text-on-surface-variant hover:text-primary transition-colors uppercase"
          >
            Privacy Policy
          </Link>
        </div>
      </div>
    </footer>
  );
};

