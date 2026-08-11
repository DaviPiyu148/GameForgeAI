import type { ProjectStatus } from '../../types';

interface StatusBadgeProps {
  status: ProjectStatus;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const config = {
    PLAYABLE: {
      color: 'text-primary',
      bg: 'bg-primary/10',
      border: 'border-primary',
      glow: 'glow-cyan',
      label: 'PLAYABLE'
    },
    COMPILING: {
      color: 'text-tertiary',
      bg: 'bg-tertiary/10',
      border: 'border-tertiary',
      glow: 'glow-amber',
      label: 'COMPILING...'
    },
    ERROR: {
      color: 'text-error',
      bg: 'bg-error/10',
      border: 'border-error',
      glow: 'glow-magenta',
      label: 'ERROR'
    }
  };

  const current = config[status];

  return (
    <div className={`inline-flex items-center px-2 py-1 text-[10px] font-mono uppercase tracking-widest border ${current.border} ${current.bg} ${current.color} ${className}`}>
      {status === 'COMPILING' && (
        <span className="w-1.5 h-1.5 rounded-full bg-tertiary mr-2 ai-pulse"></span>
      )}
      {status === 'PLAYABLE' && (
        <span className="w-1.5 h-1.5 rounded-full bg-primary mr-2"></span>
      )}
      {status === 'ERROR' && (
        <span className="w-1.5 h-1.5 rounded-full bg-error mr-2"></span>
      )}
      {current.label}
    </div>
  );
};
