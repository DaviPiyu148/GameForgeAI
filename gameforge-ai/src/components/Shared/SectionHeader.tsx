
interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({ title, subtitle, className = '' }) => {
  return (
    <div className={`mb-8 ${className}`}>
      <h2 className="text-2xl font-display text-white uppercase tracking-tight flex items-center">
        <span className="text-primary mr-3 text-xl opacity-70">&gt;</span>
        {title}
      </h2>
      {subtitle && (
        <p className="mt-2 text-on-surface-variant font-mono text-sm uppercase tracking-widest pl-7">
          // {subtitle}
        </p>
      )}
    </div>
  );
};
