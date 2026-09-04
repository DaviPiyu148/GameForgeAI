import React from 'react';

/**
 * Feature Card Icon 1: Understand Intent
 * Head/brain silhouette with an inner settings gear that rotates when hovering over the card
 * and stops when not hovering.
 */
export const BrainGearIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`w-7 h-7 text-primary ${className}`}
      aria-label="Understand Intent - Brain with rotating settings gear"
    >
      {/* Human head silhouette with brain chamber */}
      <path
        d="M9.5 2C6.5 2 4.2 4.2 4 7.2c-.8.5-1.5 1.4-1.5 2.5 0 1.2.7 2.2 1.7 2.6.1 1.2.7 2.2 1.6 2.8v1.4c0 1.1.9 2 2 2h1.7v2.5h5V18.5c1.9 0 3.5-1.6 3.5-3.5v-3.8c0-5-3.8-9.2-8.5-9.2z"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="rgba(76, 224, 210, 0.08)"
      />
      {/* Brain convolution accents */}
      <path
        d="M6 7.5c1-1 2.5-1.5 4-1.5"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeOpacity="0.5"
      />
      <path
        d="M5.5 11c1-.8 2-1 3.5-1"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeOpacity="0.5"
      />

      {/* Setting/gear inside the brain: centered at (12, 9.5) */}
      <g
        className="brain-gear-spin"
        style={{ transformOrigin: '12px 9.5px' }}
      >
        {/* Gear center axle */}
        <circle
          cx="12"
          cy="9.5"
          r="2.2"
          strokeWidth="1.5"
          fill="rgba(76, 224, 210, 0.25)"
        />
        <circle
          cx="12"
          cy="9.5"
          r="0.8"
          fill="currentColor"
        />
        {/* 8 Gear teeth radiating outward */}
        <line x1="12" y1="6" x2="12" y2="7.3" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="12" y1="11.7" x2="12" y2="13" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="8.5" y1="9.5" x2="9.8" y2="9.5" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="14.2" y1="9.5" x2="15.5" y2="9.5" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="9.5" y1="7" x2="10.4" y2="7.9" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="13.6" y1="11.1" x2="14.5" y2="12" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="9.5" y1="12" x2="10.4" y2="11.1" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="13.6" y1="7.9" x2="14.5" y2="7" strokeWidth="1.8" strokeLinecap="round" />
      </g>
    </svg>
  );
};

/**
 * Feature Card Icon 2: Multi-Signal Ranking
 * Target/goal with an arrow moving towards the goal on hover and stopping when not hovering.
 */
export const TargetArrowIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`w-7 h-7 text-secondary ${className}`}
      aria-label="Multi-Signal Ranking - Arrow moving towards goal"
    >
      {/* Target Goal (centered at 15, 12) */}
      <g className="target-goal-group">
        {/* Outer target ring */}
        <circle
          cx="15"
          cy="12"
          r="6.5"
          strokeWidth="1.4"
          strokeDasharray="2 1.5"
          strokeOpacity="0.8"
        />
        {/* Middle target ring */}
        <circle
          cx="15"
          cy="12"
          r="3.8"
          strokeWidth="1.4"
          strokeOpacity="0.9"
        />
        {/* Center Bullseye Goal */}
        <circle
          cx="15"
          cy="12"
          r="1.7"
          fill="currentColor"
          className="target-bullseye-pulse"
          style={{ transformOrigin: '15px 12px' }}
        />
      </g>

      {/* Arrow moving towards the goal (starts at left, points right towards 15, 12) */}
      <g className="arrow-moving-to-goal">
        {/* Feather fletching */}
        <path
          d="M2.2 10.2L3.8 12L2.2 13.8"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Arrow shaft */}
        <line
          x1="3"
          y1="12"
          x2="9"
          y2="12"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        {/* Arrow head */}
        <path
          d="M7 9.5L10 12L7 14.5"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="currentColor"
        />
      </g>
    </svg>
  );
};

/**
 * Feature Card Icon 3: Build & Remix
 * Dynamic fire burning animation with multi-tiered flickering flame tongues and rising embers.
 */
export const FireBurningIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`w-7 h-7 ${className}`}
      aria-label="Build & Remix - Burning fire animation"
    >
      {/* Outer Flame (burning orange-red) */}
      <path
        d="M12 2C10.5 4.5 9 6.5 9 9c0 1.2.4 2.3 1 3.2C8 11.5 7 10 7 8c-2 2.5-3 5.5-3 8 0 4.4 3.6 8 8 8s8-3.6 8-8c0-3.5-1.5-6.5-3.5-9-.5 1.5-1.5 2.5-2.5 3 0-2.5-1-5.5-2-8z"
        fill="#ff5722"
        className="fire-outer-flame"
        style={{ transformOrigin: '12px 22px' }}
      />

      {/* Middle Flame Tongue (warm golden amber) */}
      <path
        d="M12 6.5c-1 1.8-2 3.2-2 5 0 .9.3 1.6.7 2.3-.7-.5-1.5-1.4-1.5-2.8-.9 1.6-1.4 3.2-1.4 4.5 0 2.8 1.8 5 4.2 5s4.2-2.2 4.2-5c0-2-.7-3.8-1.8-5-.3.9-.9 1.6-1.4 2 0-1.6-.6-3.6-1-6z"
        fill="#ffc24c"
        className="fire-mid-flame"
        style={{ transformOrigin: '12px 21px' }}
      />

      {/* Core Flame (bright hot golden core) */}
      <path
        d="M12 12.5c-.6 1-1.1 1.8-1.1 2.8 0 1.5.8 2.7 1.8 2.7s1.8-1.2 1.8-2.7c0-1-.5-1.8-1.2-2.5-.2.5-.5.8-.8 1 0-.6-.3-1.4-.5-1.9z"
        fill="#fff9c4"
        className="fire-core-flame"
        style={{ transformOrigin: '12px 20px' }}
      />

      {/* Rising Embers / Sparks */}
      <circle
        cx="9"
        cy="4"
        r="0.75"
        fill="#ffe082"
        className="fire-ember-left"
      />
      <circle
        cx="14.5"
        cy="3.2"
        r="0.65"
        fill="#ffb74d"
        className="fire-ember-right"
      />
    </svg>
  );
};
