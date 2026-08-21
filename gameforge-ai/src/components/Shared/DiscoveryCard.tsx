
interface DiscoveryCardProps {
  id: string;
  title: string;
  creator: string;
  matchPercentage: number;
  onClick?: () => void;
  className?: string;
}

export const DiscoveryCard: React.FC<DiscoveryCardProps> = ({ 
  title, 
  creator, 
  matchPercentage, 
  onClick,
  className = '' 
}) => {
  return (
    <div 
      className={`border border-outline-variant bg-surface hover:border-primary transition-colors cursor-pointer group p-4 flex flex-col gap-3 relative overflow-hidden ${className}`}
      onClick={onClick}
    >
      <div className="absolute top-0 left-0 w-full h-1 bg-primary transform scale-x-0 group-hover:scale-x-100 transition-transform origin-left"></div>
      
      <div className="flex justify-between items-start">
        <h3 className="font-body font-bold text-white group-hover:text-primary transition-colors text-lg">
          {title}
        </h3>
        <div className="flex items-center gap-1 text-xs font-mono text-primary bg-primary/10 px-2 py-1">
          <span className="material-symbols-outlined text-[14px]">radar</span>
          {matchPercentage}%
        </div>
      </div>
      
      <div className="text-sm font-mono text-on-surface-variant">
        BY: <span className="text-white">{creator}</span>
      </div>
      
      <div className="w-full h-32 bg-surface-container mt-2 border border-outline-variant flex items-center justify-center">
         <span className="material-symbols-outlined text-3xl text-on-surface-variant opacity-30">videogame_asset</span>
      </div>
    </div>
  );
};
