import type { ReactNode } from 'react';

interface TerminalPaneProps {
  title?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export const TerminalPane: React.FC<TerminalPaneProps> = ({
  title = 'TERMINAL',
  children,
  className = '',
  bodyClassName = ''
}) => {
  return (
    <div className={`flex flex-col border border-outline-variant bg-surface overflow-hidden ${className}`}>
      {/* Terminal Header */}
      <div className="flex items-center px-4 py-2 bg-terminal-header border-b border-outline-variant select-none">
        <div className="flex space-x-2 mr-4">
          <div className="w-3 h-3 rounded-full bg-error/80"></div>
          <div className="w-3 h-3 rounded-full bg-tertiary/80"></div>
          <div className="w-3 h-3 rounded-full bg-primary/80"></div>
        </div>
        <div className="text-xs font-mono text-on-surface-variant tracking-widest">{title}</div>
      </div>
      
      {/* Terminal Body */}
      <div className={`flex-1 p-4 bg-terminal-bg text-primary font-mono overflow-auto ${bodyClassName}`}>
        {children}
      </div>
    </div>
  );
};
