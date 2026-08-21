
interface ParameterControlProps {
  label: string;
  type?: 'slider' | 'toggle';
  value: number | boolean;
  onChange: (value: any) => void;
  min?: number;
  max?: number;
  className?: string;
}

export const ParameterControl: React.FC<ParameterControlProps> = ({
  label,
  type = 'slider',
  value,
  onChange,
  min = 0,
  max = 100,
  className = ''
}) => {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="flex justify-between items-center text-xs font-mono text-on-surface-variant uppercase tracking-wider">
        <span>{label}</span>
        <span className="text-primary">{typeof value === 'boolean' ? (value ? 'ON' : 'OFF') : value}</span>
      </div>
      
      {type === 'slider' ? (
        <input 
          type="range" 
          min={min} 
          max={max} 
          value={value as number} 
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-1 bg-surface-container-high appearance-none outline-none focus:glow-cyan slider-thumb-primary"
        />
      ) : (
        <div 
          className={`w-12 h-6 border cursor-pointer transition-colors flex items-center px-1 ${value ? 'border-primary bg-primary/10' : 'border-outline-variant bg-surface-container'}`}
          onClick={() => onChange(!value)}
        >
          <div className={`w-4 h-4 bg-primary transition-transform ${value ? 'translate-x-5' : 'bg-outline-variant'}`}></div>
        </div>
      )}
    </div>
  );
};
