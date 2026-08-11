# GameForge AI - Consolidated Design System

This document outlines the consolidated design system for GameForge AI, establishing a single source of truth based on the reference HTML and screenshots in the workspace, while noting deviations from the initial Stitch (Obsidian Forge) project specifications.

## 1. Overall Visual Style
**Retro-Futuristic Terminal / Cyberpunk**
The UI leans heavily into a "hacker/developer" aesthetic tailored for gamers and AI-builders. It features a dark, immersive environment characterized by neon glows, scanline overlays, visible pane borders, and terminal-like window structures.

*Comparison with Stitch:* The Stitch project defined a "Soft-Tech" and "Technical Minimalism" style with large rounded corners and tonal layering. The reference implementation pivots to a more aggressive, retro-futuristic, and highly stylized cyber aesthetic with sharper edges and intense neon glows.

## 2. Color Palette
The color scheme shifts from the Stitch project's Violet/Cyan pairing to a vibrant tri-color neon palette against a deep dark background.

*   **Background:** `#0a0d14` (Deep void black/blue)
*   **Surfaces:** `#10131a` (Level 1), `#191b23` / `#1e2233` (Level 2/Headers)
*   **Primary Accent (Cyan):** `#4ce0d2` - Used for primary UI elements, terminal text, borders, and general glowing accents.
*   **Secondary Accent (Magenta):** `#ff3d81` / `#c9005b` - Used for primary action buttons, highlights, and critical states.
*   **Tertiary Accent (Amber):** `#ffc24c` - Used for secondary actions, icons, and warnings.
*   **Text (On-Background):** `#e5e1e4` (Primary), `#bbcac6` / `#859491` (Muted/Variants)

## 3. Typography
A strict three-font strategy is employed to separate display, reading, and technical contexts.

*   **Headlines & Display (`display-lg`, `headline-lg`):** *Press Start 2P* - Used for major section titles and brand identity to enforce the retro-gaming vibe. (Overrides Stitch's "Inter").
*   **Body Content (`body-md`):** *Space Grotesk* - Used for readable paragraph text, offering a geometric and slightly technical feel. (Overrides Stitch's "Inter").
*   **Technical & Labels (`label-mono`):** *JetBrains Mono* - Used for navigation links, buttons, terminal inputs, metadata, and code. (Consistent with Stitch).

## 4. Spacing System
Follows a strict baseline grid:
*   `base`: 4px
*   `stack-sm`: 8px
*   `stack-md` / `gutter`: 16px
*   `container-margin`: 24px
*   `stack-lg`: 32px

## 5. Borders & Corner Radii
*   **Borders:** Heavy use of 1px solid borders (`pane-border`) for structural division, utilizing accent colors (`#4ce0d2`, `#ff3d81`) or muted structural colors (`#3c4947`).
*   **Radii:** Deviates from Stitch's 16px-24px rounded corners. Elements are either sharp (0px) or utilize very tight rounding (0.125rem to 0.25rem / 2px to 4px) to maintain the terminal aesthetic, with occasional pill-shapes for chips/badges.

## 6. Shadows, Glows, and Effects
*   **Text Glow:** Classes like `.glow-cyan`, `.glow-magenta`, and `.glow-amber` apply a `text-shadow: 0 0 10px [color]` effect.
*   **Box Glow:** Classes like `.glow-box-cyan` apply a `box-shadow: 0 0 15px rgba(..., 0.3)` coupled with a 1px solid border.
*   **Scanlines:** A global `::before` or `.scanline` pseudo-element applies a subtle, fixed scanline gradient overlay over the entire application.
*   **Glassmorphism:** Navigation bars use `backdrop-filter: blur(12px)` over a semi-transparent dark background (e.g., `rgba(10, 13, 20, 0.8)`), consistent with Stitch.

## 7. UI Components

### Navigation Structure
*   Docked top navigation with a glassmorphic background.
*   Logo and brand name (Press Start 2P) on the left.
*   Center navigation links use JetBrains Mono, uppercase. Active states use a bottom border.
*   Right side contains primary action buttons (e.g., "Build a Game") and user avatar.

### Buttons
*   **Primary Action:** Solid background (often Magenta) with white/dark text, uppercase JetBrains Mono, and a bounding glow on hover.
*   **Secondary/Terminal:** Outlined buttons with a colored border and transparent background, filling with a low-opacity color on hover.

### Terminal / Code-Editor Components
*   A signature component of the UI.
*   Features a distinct header bar (e.g., `#1e2233`) mimicking a window title bar, often with faux window controls (colored dots).
*   Body is solid dark (`#10131a`) with JetBrains Mono text in Cyan or Green.
*   Inputs feature a blinking cursor animation (`.cursor-blink`).
*   Line numbers and token counters are integrated for a "developer environment" feel.

### Status Indicators
*   Pulsing dots (`.ai-pulse`) next to text labels (e.g., "SYS_ONLINE").
*   Use of brackets for system logs, e.g., `[SYS]`, `[MOD]`.

### Forms & Inputs
*   Inputs are styled as command-line prompts (e.g., `~ $`).
*   Border-less text areas that glow (via `focus-within`) when active.
*   Range sliders customized with sharp tracks and accent colors for thumbs.
*   Custom toggle switches that replace standard checkboxes.

## 8. Layout & Reusable Patterns
*   **Bento Grids:** Used on the homepage for feature highlights, wrapping content in glowing, bordered boxes.
*   **IDE Layout:** The builder utilizes a classic IDE layout with a fixed sidebar, top nav, main editor pane, and a bottom compiler output terminal, separated by rigid 1px borders.
