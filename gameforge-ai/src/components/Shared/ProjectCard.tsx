import type { GameProject } from '../../types';
import { StatusBadge } from './StatusBadge';
import { TerminalPane } from './TerminalPane';

interface ProjectCardProps {
  project: GameProject;
  onClick?: (project: GameProject) => void;
  className?: string;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick, className = '' }) => {
  return (
    <TerminalPane 
      title={`[PRJ]_${project.id}`}
      className={`hover:border-primary transition-colors cursor-pointer group ${className}`}
    >
      <div 
        className="flex flex-col h-full gap-4"
        onClick={() => onClick && onClick(project)}
      >
        <div className="flex justify-between items-start">
          <h3 className="font-display text-sm text-white group-hover:text-primary transition-colors">
            {project.title}
          </h3>
          <StatusBadge status={project.status} />
        </div>
        
        <div className="flex-1 mt-2">
          <div className="w-full h-24 bg-surface-container-high border border-outline-variant flex items-center justify-center opacity-50 group-hover:opacity-100 transition-opacity">
            <span className="material-symbols-outlined text-4xl text-on-surface-variant">image</span>
          </div>
        </div>
        
        <div className="text-xs font-mono text-on-surface-variant flex justify-between items-end border-t border-outline-variant/50 pt-2">
          <span className="truncate max-w-[60%]">ENG: {project.parameters.engine.substring(0, 10)}...</span>
          <span className="text-primary/70">{project.lastModified}</span>
        </div>
      </div>
    </TerminalPane>
  );
};
