import React from 'react';

/**
 * Feature Card Icon 1: Understand Intent
 * 100% Authentic Google Material Symbol skull with cogwheel inside.
 * The cogwheel rotates smoothly around its center on card hover and stops when not hovering.
 */
export const BrainGearIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 -960 960 960"
      className={`w-7 h-7 text-primary select-none overflow-visible ${className}`}
      fill="currentColor"
      aria-label="Understand Intent - Cogwheel inside skull"
    >
      {/* Authentic Google Material Symbol Skull / Head Outline */}
      <path d="M240-80v-172q-57-52-88.5-121.5T120-520q0-150 105-255t255-105q125 0 221.5 73.5T827-615l52 205q5 19-7 34.5T840-360h-80v120q0 33-23.5 56.5T680-160h-80v80h-80v-160h160v-200h108l-38-155q-23-91-98-148t-172-57q-116 0-198 81t-82 197q0 60 24.5 114t69.5 96l26 24v208h-80Z" />

      {/* Authentic Google Material Symbol Cogwheel / Gear: centered at (480px, -520px) */}
      <g
        className="brain-gear-spin"
        style={{ transformOrigin: '480px -520px' }}
      >
        <path d="M440-360h80l6-50q8-3 14.5-7t11.5-9l46 20 40-68-40-30q2-8 2-16t-2-16l40-30-40-68-46 20q-5-5-11.5-9t-14.5-7l-6-50h-80l-6 50q-8 3-14.5 7t-11.5 9l-46-20-40 68 40 30q-2 8-2 16t2 16l-40 30 40 68 46-20q5 5 11.5 9t14.5 7l6 50Zm40-100q-25 0-42.5-17.5T420-520q0-25 17.5-42.5T480-580q25 0 42.5 17.5T540-520q0 25-17.5 42.5T480-460Z" />
      </g>
    </svg>
  );
};

/**
 * Feature Card Icon 2: Multi-Signal Ranking
 * Target/goal with an arrow moving towards the goal on hover and stopping when not hovering.
 * (Confirmed good by user)
 */
export const TargetArrowIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`w-7 h-7 text-secondary select-none overflow-visible ${className}`}
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
 * Bonfire with crossed wooden logs at the base and dynamic burning flames rising upward.
 * Styled in the clean amber outline aesthetic matching the other icons with zero dark square artifacts.
 */
export const FireBurningIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`w-7 h-7 text-tertiary select-none overflow-visible ${className}`}
      aria-label="Build & Remix - Bonfire with burning fire"
    >
      {/* Bonfire Base: Crossed Wooden Logs (anchored at base) */}
      <g className="bonfire-logs" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        {/* Left log (slanted upward to the right) */}
        <path d="M4 20.5L20 15.5" strokeOpacity="0.9" />
        <ellipse cx="4" cy="20.5" rx="1.2" ry="0.8" fill="currentColor" fillOpacity="0.4" />
        {/* Right log (slanted upward to the left, crossed over) */}
        <path d="M20 20.5L4 15.5" strokeOpacity="0.9" />
        <ellipse cx="20" cy="20.5" rx="1.2" ry="0.8" fill="currentColor" fillOpacity="0.4" />
        {/* Embers bed beneath logs */}
        <path d="M8 21.5h8" strokeOpacity="0.6" strokeWidth="1.2" strokeDasharray="1.5 1.5" />
      </g>

      {/* Burning Fire: Leaping Flame Tongues Rising from the Logs */}
      <g className="bonfire-flame-group">
        {/* Outer Flame Tongue */}
        <path
          d="M12 3C10.5 5.5 8.5 7.5 8.5 11c0 2 1 3.5 1.5 4.5-.8-.5-1.5-1.5-1.5-3 0-1 .4-2 .8-2.8-2 2-2.8 4.3-2.8 6.3 0 3 2.5 5 5.5 5s5.5-2 5.5-5c0-2.2-1-4.5-2.8-6.3.4.8.8 1.8.8 2.8 0 1.5-.7 2.5-1.5 3 .5-1 1.5-2.5 1.5-4.5 0-3.5-2-5.5-3.5-8z"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="rgba(255, 194, 76, 0.12)"
          className="bonfire-flame-outer"
          style={{ transformOrigin: '12px 19px' }}
        />

        {/* Inner Flame Core (hotter inner dancing flame) */}
        <path
          d="M12 9c-.8 1.5-1.8 2.8-1.8 4.5 0 1.5.8 2.8 1.8 3.5 1-.7 1.8-2 1.8-3.5 0-1.7-1-3-1.8-4.5z"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="rgba(255, 194, 76, 0.35)"
          className="bonfire-flame-inner"
          style={{ transformOrigin: '12px 17px' }}
        />

        {/* Rising Bonfire Sparks / Embers */}
        <circle cx="10" cy="5" r="0.75" fill="currentColor" className="bonfire-spark-1" />
        <circle cx="14" cy="4" r="0.65" fill="currentColor" className="bonfire-spark-2" />
        <circle cx="12" cy="1.5" r="0.5" fill="currentColor" className="bonfire-spark-3" />
      </g>
    </svg>
  );
};
