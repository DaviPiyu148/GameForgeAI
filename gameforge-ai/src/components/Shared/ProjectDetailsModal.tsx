import { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import type { GameProject } from '../../types';

interface ProjectDetailsModalProps {
  project: GameProject;
  onClose: () => void;
}

export const ProjectDetailsModal = ({ project, onClose }: ProjectDetailsModalProps) => {
  const [isClosing, setIsClosing] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  const handleClose = useCallback(() => {
    setIsClosing(true);
    setTimeout(() => {
      onClose();
    }, 250);
  }, [onClose]);

  useEffect(() => {
    closeBtnRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isClosing) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isClosing, handleClose]);

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !isClosing) {
      handleClose();
    }
  };

  return createPortal(
    <div 
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm ${isClosing ? 'modal-backdrop-exit' : 'modal-backdrop-enter'}`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label={`Details for ${project.title}`}
    >
      <div 
        className={`w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-surface border border-primary/50 rounded-sm flex flex-col shadow-[0_0_30px_rgba(76,224,210,0.15)] glow-cyan ${isClosing ? 'modal-exit' : 'modal-enter'}`}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-terminal-header border-b border-primary/30 p-3 flex justify-between items-center">
          <div className="flex items-center gap-2 text-primary">
            <span className="material-symbols-outlined" aria-hidden="true">info</span>
            <span className="font-mono text-sm tracking-widest font-bold uppercase">PROJECT_DETAILS.DAT</span>
          </div>
          <button 
            ref={closeBtnRef}
            onClick={handleClose}
            className="text-on-surface-variant icon-interactive hover:text-primary transition-colors p-1 focus:outline-none focus:ring-1 focus:ring-primary"
            aria-label="Close details"
          >
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>
        
        {/* Body */}
        <div className="p-6 bg-terminal-bg font-mono space-y-6">
          <div className="flex justify-between items-start border-b border-outline-variant/30 pb-4">
            <div>
              <h2 className="text-xl text-primary uppercase font-display tracking-wider mb-1">{project.title}</h2>
              <div className="flex gap-3 text-xs text-on-surface-variant">
                <span>ID: {project.id}</span>
                <span>•</span>
                <span>{project.genre}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 border border-primary/30 uppercase">
                {project.status}
              </span>
              <span className="text-[10px] text-outline">Modified: {project.lastModified}</span>
            </div>
          </div>
          
          <div className="space-y-2">
            <h3 className="text-xs text-secondary uppercase tracking-widest">Original Prompt</h3>
            <div className="bg-surface-container-low border border-outline-variant/50 p-3 text-sm text-on-surface/90 max-h-32 overflow-y-auto whitespace-pre-wrap">
              {project.prompt}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-3">
              <h3 className="text-xs text-secondary uppercase tracking-widest">Build Specs</h3>
              <div className="space-y-1 text-xs text-on-surface-variant">
                <div className="flex justify-between border-b border-outline-variant/20 pb-1">
                  <span>Engine:</span>
                  <span className="text-on-surface">{project.parameters.engine}</span>
                </div>
                {project.runtimeMetadata?.model && (
                  <div className="flex justify-between border-b border-outline-variant/20 pb-1">
                    <span>AI Model:</span>
                    <span className="text-primary font-bold">
                      {project.runtimeMetadata.model.includes('gemma-4-31b-it')
                        ? 'Gemma 4 31B'
                        : project.runtimeMetadata.model}
                    </span>
                  </div>
                )}
                <div className="flex justify-between border-b border-outline-variant/20 pb-1">
                  <span>Art Density:</span>
                  <span className="text-on-surface">{project.parameters.artDensity}%</span>
                </div>
                <div className="flex justify-between border-b border-outline-variant/20 pb-1">
                  <span>Physics:</span>
                  <span className="text-on-surface">{project.parameters.physics}%</span>
                </div>
              </div>
            </div>
            
            <div className="space-y-3">
              <h3 className="text-xs text-secondary uppercase tracking-widest">Logic Modules</h3>
              <div className="flex flex-wrap gap-2">
                {project.parameters.modules.length > 0 ? (
                  project.parameters.modules.map(mod => (
                    <span key={mod} className="text-[10px] bg-surface-container-highest border border-outline-variant px-2 py-1 uppercase text-on-surface">
                      {mod}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-outline italic">None active</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
