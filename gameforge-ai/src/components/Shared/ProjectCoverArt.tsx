/**
 * ProjectCoverArt — renders a deterministic procedural cover for a GameProject.
 *
 * Drop-in replacement for the static cyan-grid placeholder in project cards.
 * Produces a gradient background + icon + label. Fully self-contained:
 * no image loading, no network requests, stable across re-renders.
 */
import { generateProjectCover } from '../../utils/projectCover';
import type { GameProject } from '../../types';

interface Props {
  project: GameProject;
  /** Optional CSS class additions for layout/sizing overrides. */
  className?: string;
}

export function ProjectCoverArt({ project, className = '' }: Props) {
  const cover = generateProjectCover(project);

  return (
    <div
      className={`relative overflow-hidden flex flex-col items-center justify-center group-hover:brightness-110 transition-all ${className}`}
      style={{ background: cover.gradient }}
      aria-hidden="true"
    >
      {/* Subtle grid overlay — matches GameForge visual language */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Corner accent lines */}
      <div
        className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 opacity-60"
        style={{ borderColor: cover.accentColor }}
      />
      <div
        className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 opacity-60"
        style={{ borderColor: cover.accentColor }}
      />

      {/* Main icon */}
      <span
        className="material-symbols-outlined relative z-10 text-5xl mb-1 drop-shadow-lg"
        style={{ color: cover.accentColor }}
      >
        {cover.icon}
      </span>

      {/* Genre / mode label */}
      <span
        className="relative z-10 font-mono text-[9px] tracking-widest uppercase opacity-80 mt-0.5"
        style={{ color: cover.accentColor }}
      >
        {cover.label}
      </span>
    </div>
  );
}
