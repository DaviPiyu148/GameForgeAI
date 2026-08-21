
interface ProgressBarProps {
  progress: number; // 0 to 100
  label?: string;
  status?: 'normal' | 'success' | 'error';
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ 
  progress, 
  label, 
  status = 'normal',
  className = ''
}) => {
  const colorMap = {
    normal: 'bg-primary glow-cyan',
    success: 'bg-primary glow-cyan',
    error: 'bg-error glow-magenta'
  };

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <div className="flex justify-between items-end mb-2">
          <span className="text-xs font-mono text-on-surface-variant uppercase tracking-wider">{label}</span>
          <span className="text-xs font-mono text-primary">{Math.round(progress)}%</span>
        </div>
      )}
      <div className="h-1 bg-surface-container-high w-full overflow-hidden border border-outline-variant">
        <div 
          className={`h-full transition-all duration-300 ${colorMap[status]}`} 
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};
