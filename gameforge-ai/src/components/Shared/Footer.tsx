import React from 'react';
import { useAppContext } from '../../context/AppContext';

export const Footer: React.FC = () => {
  const { openInfoModal } = useAppContext();

  return (
    <footer className="bg-surface-container-lowest w-full py-8 mt-auto border-t border-outline-variant z-10 relative">
      <div className="max-w-[1080px] mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="font-mono text-[10px] text-primary uppercase tracking-widest">
          © 2026 GAMEFORGE_AI // CORE_V1.0.2
        </div>
        <div className="flex flex-wrap justify-center gap-4">
          <button
            type="button"
            onClick={() => openInfoModal('docs')}
            className="font-mono text-[10px] text-on-surface-variant/60 hover:text-primary transition-colors uppercase cursor-pointer"
          >
            Documentation
          </button>
          <button
            type="button"
            onClick={() => openInfoModal('api')}
            className="font-mono text-[10px] text-on-surface-variant/60 hover:text-primary transition-colors uppercase cursor-pointer"
          >
            API Access
          </button>
          <button
            type="button"
            onClick={() => openInfoModal('community')}
            className="font-mono text-[10px] text-on-surface-variant/60 hover:text-primary transition-colors uppercase cursor-pointer"
          >
            Community
          </button>
          <button
            type="button"
            onClick={() => openInfoModal('support')}
            className="font-mono text-[10px] text-on-surface-variant/60 hover:text-primary transition-colors uppercase cursor-pointer"
          >
            Support
          </button>
          <button
            type="button"
            onClick={() => openInfoModal('privacy')}
            className="font-mono text-[10px] text-on-surface-variant/60 hover:text-primary transition-colors uppercase cursor-pointer"
          >
            Privacy Policy
          </button>
        </div>
      </div>
    </footer>
  );
};
