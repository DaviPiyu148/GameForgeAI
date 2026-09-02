import React from 'react';
import type { GameProject, ProjectVersionSummary } from '../../types';
import { ProjectStudioModal } from './ProjectStudioModal';

export interface ProjectDetailsModalProps {
  project: GameProject;
  onClose: () => void;
  onPlayCurrent?: () => void;
  onRemix?: () => void;
  onEditInBuilder?: () => void;
  onPlayHistoricalVersion?: (version: ProjectVersionSummary) => void;
  onProjectUpdated?: (updated: GameProject) => void;
}

/**
 * @deprecated Use ProjectStudioModal directly.
 */
export const ProjectDetailsModal: React.FC<ProjectDetailsModalProps> = ({
  project,
  onClose,
  onPlayCurrent = () => {},
  onRemix = () => {},
  onEditInBuilder = () => {},
  onPlayHistoricalVersion = () => {},
  onProjectUpdated = () => {},
}) => {
  return (
    <ProjectStudioModal
      project={project}
      onClose={onClose}
      onPlayCurrent={onPlayCurrent}
      onRemix={onRemix}
      onEditInBuilder={onEditInBuilder}
      onPlayHistoricalVersion={onPlayHistoricalVersion}
      onProjectUpdated={onProjectUpdated}
    />
  );
};

