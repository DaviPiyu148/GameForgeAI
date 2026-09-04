import React, { useState } from 'react';
import type { BackendSavedDiscovery } from '../../types';
import { useAppContext } from '../../context/AppContext';

interface SavedDiscoveryCoverProps {
  discovery: BackendSavedDiscovery;
  className?: string;
  iconClassName?: string;
}

export const SavedDiscoveryCover: React.FC<SavedDiscoveryCoverProps> = ({
  discovery,
  className = 'w-full h-full object-cover',
  iconClassName = 'material-symbols-outlined text-2xl text-secondary/40',
}) => {
  const { state } = useAppContext();
  const [hasFailed, setHasFailed] = useState(false);

  // Fallback hierarchy:
  // 1. Explicitly persisted cover/header URL
  // 2. Known catalog/enrichment image from active discovery results
  // 3. Steam CDN fallback based on steam_app_id
  // 4. Stylized placeholder
  const matchingResult = (state.discoveryResults || []).find(
    (r) => (r.game.external_id || r.game.id) === discovery.steam_app_id
  );

  const primaryUrl = (discovery as unknown as { header_image?: string }).header_image;
  const catalogUrl =
    matchingResult?.game?.hero_image_url ||
    matchingResult?.game?.cover_image_url ||
    matchingResult?.game?.enrichment?.cover_url;
  const steamCdnUrl = discovery.steam_app_id
    ? `https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/${discovery.steam_app_id}/header.jpg`
    : null;

  const resolvedUrl = primaryUrl || catalogUrl || steamCdnUrl;

  if (hasFailed || !resolvedUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-dim">
        <span className={iconClassName} aria-hidden="true">
          sports_esports
        </span>
      </div>
    );
  }

  return (
    <img
      src={resolvedUrl}
      alt={discovery.title}
      className={className}
      loading="lazy"
      onError={() => setHasFailed(true)}
    />
  );
};
