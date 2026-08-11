import { useEffect, useRef } from 'react';

interface PrototypeModalProps {
  onClose: () => void;
}

export const PrototypeModal = ({ onClose }: PrototypeModalProps) => {
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // Focus the close button when opened
    closeBtnRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // If the click is exactly on the backdrop (not bubbling up from children)
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Simulated Frontend Prototype"
    >
      <div 
        className="w-full max-w-4xl bg-surface border-2 border-primary rounded-lg overflow-hidden flex flex-col shadow-[0_0_50px_rgba(76,224,210,0.2)]"
        // Prevent clicks inside the modal from bubbling to the backdrop
        onClick={e => e.stopPropagation()}
      >
        <div className="bg-terminal-header border-b border-primary/30 p-3 flex justify-between items-center">
          <div className="flex items-center gap-3 text-primary">
            <span className="material-symbols-outlined animate-pulse" aria-hidden="true">videogame_asset</span>
            <span className="font-mono text-sm tracking-widest font-bold">SIMULATED FRONTEND PROTOTYPE</span>
          </div>
          <button 
            ref={closeBtnRef}
            onClick={onClose}
            className="text-on-surface-variant hover:text-error transition-colors p-1 rounded focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Close prototype preview"
          >
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>
        
        <div className="aspect-video bg-terminal-bg flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute inset-0 scanline-effect opacity-30 pointer-events-none"></div>
          
          <div className="w-24 h-24 mb-6 relative">
            <div className="absolute inset-0 border-4 border-primary rounded-full animate-[spin_3s_linear_infinite] border-t-transparent"></div>
            <div className="absolute inset-2 border-4 border-secondary rounded-full animate-[spin_2s_linear_infinite_reverse] border-b-transparent"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="material-symbols-outlined text-4xl text-primary ai-pulse" aria-hidden="true">rocket_launch</span>
            </div>
          </div>
          
          <h2 className="font-display text-2xl text-on-surface text-glow-cyan mb-2 text-center">MOCK GAME PREVIEW</h2>
          <p className="font-mono text-sm text-on-surface-variant max-w-lg text-center leading-relaxed px-4">
            This is a simulated frontend prototype. Actual game engine execution (UE5/Unity) and full AI synthesis are not connected in this demonstration.
          </p>
        </div>
      </div>
    </div>
  );
};
