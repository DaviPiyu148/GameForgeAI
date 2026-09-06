---
name: GameForge AI
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363941'
  surface-container-lowest: '#0b0e15'
  surface-container-low: '#191b23'
  surface-container: '#1d1f27'
  surface-container-high: '#272a32'
  surface-container-highest: '#32353d'
  on-surface: '#e1e2ec'
  on-surface-variant: '#cbc3d7'
  inverse-surface: '#e1e2ec'
  inverse-on-surface: '#2d3038'
  outline: '#859491'
  outline-variant: '#3c4947'
  surface-tint: '#46dcce'
  primary: '#6ffdee'
  on-primary: '#003733'
  primary-container: '#4ce0d2'
  on-primary-container: '#006059'
  inverse-primary: '#006a62'
  secondary: '#ffb1c2'
  on-secondary: '#66002b'
  secondary-container: '#c9005b'
  on-secondary-container: '#ffdbe1'
  tertiary: '#ffe4b9'
  on-tertiary: '#422d00'
  tertiary-container: '#fec14b'
  on-tertiary-container: '#714f00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#69f8ea'
  primary-fixed-dim: '#46dcce'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#00504a'
  secondary-fixed: '#ffd9df'
  secondary-fixed-dim: '#ffb1c2'
  on-secondary-fixed: '#3f0018'
  on-secondary-fixed-variant: '#8f003f'
  tertiary-fixed: '#ffdea9'
  tertiary-fixed-dim: '#f9bc47'
  on-tertiary-fixed: '#271900'
  on-tertiary-fixed-variant: '#5e4200'
  background: '#10131a'
  on-background: '#e1e2ec'
  surface-variant: '#32353d'
  terminal-bg: '#10131a'
  terminal-header: '#1e2233'
  scanline-overlay: rgba(255, 255, 255, 0.05)
typography:
  display-lg:
    fontFamily: Press Start 2P
    fontSize: 32px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Press Start 2P
    fontSize: 24px
    fontWeight: '400'
    lineHeight: '1.4'
  headline-lg-mobile:
    fontFamily: Press Start 2P
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.4'
  body-md:
    fontFamily: Space Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  label-mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: '1.2'
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  stack-sm: 8px
  stack-md: 16px
  gutter: 16px
  container-margin: 24px
  stack-lg: 32px
---

## Brand & Style
GameForge AI is a high-octane, developer-centric platform for game discovery and prototyping. The brand personality is "Retro-Futuristic Terminal"—merging the gritty, functional aesthetic of a Command Line Interface (CLI) with the vibrant, high-energy visuals of 80s arcade and cyberpunk culture.

The design style is a hybrid of **Brutalism** and **Glassmorphism**. It utilizes heavy borders, monospaced typography, and scanline overlays to establish a technical foundation, while employing vibrant neon glows and backdrop blurs to create depth and a "high-tech" feel. The emotional response should be one of "empowered creativity," making the user feel like a "god-mode" developer crafting worlds from a terminal.

## Colors
The palette is rooted in a deep "Void Black" (#0a0d14) background to maximize the impact of neon accents. 

- **Cyber Cyan (Primary):** Used for primary actions, success states, and terminal prompts. It represents the "system" and core logic.
- **Neon Magenta (Secondary):** Used for highlighting "magic" or AI-driven creation elements and high-priority call-to-actions.
- **Amber Alert (Tertiary):** Used for warnings, interactive chips, and secondary highlights to provide a triadic color balance.
- **Deep Slate (Surface):** Terminal containers use a slightly elevated, desaturated navy-slate to distinguish functional areas from the background.

The interface utilizes a global scanline overlay (linear gradients) and text-shadows to simulate a CRT monitor glow.

## Typography
Typography is the primary driver of the "GameForge" identity. We use three distinct families:
1. **Press Start 2P:** Reserved for major displays and headlines. It should always be uppercase to maintain the arcade aesthetic.
2. **Space Grotesk:** Used for body copy and descriptions. Its geometric but slightly idiosyncratic forms bridge the gap between technical and human.
3. **JetBrains Mono:** Used for all functional labels, buttons, and terminal inputs. This reinforces the "developer" mental model.

All monospaced text should leverage `letter-spacing` to improve legibility and "code-like" appearance. Cyan and Magenta glows should be applied sparingly to `display` and `headline` roles.

## Layout & Spacing
The system uses a **fixed-width container model** for hero content (max-width 4xl to 5xl) and a **fluid grid** for the features section. 

- **Grid:** A standard 12-column grid for desktop, collapsing to 1 column for mobile. 
- **Rhythm:** An 8px-based spacing scale is used for vertical rhythm, though 4px "base" units are used for tight terminal elements.
- **Gutters:** Standard 16px (gutter) for internal component spacing and 24px (container-margin) for page-level horizontal safe areas.
- **Reflow:** On mobile, padding is reduced by 25%, and display font sizes scale down significantly (e.g., Display LG 32px -> 16px).

## Elevation & Depth
Depth is created through **Chroma Glows** rather than standard shadows.
- **Level 0 (Background):** Solid #0a0d14 with scanline overlay.
- **Level 1 (Containers):** Solid #10131a with a 1px solid border in the theme color (Cyan, Magenta, or Amber).
- **Interactive Elevation:** Elevated elements use a `box-shadow` that matches the border color with 30% opacity (e.g., `0 0 15px rgba(76, 224, 210, 0.3)`).
- **Glass Effects:** Navigation bars and sticky elements use `backdrop-filter: blur(12px)` combined with a semi-transparent version of the background color (80% opacity).

## Shapes
Shapes are generally **Soft-Angular**. While the terminal aesthetic suggests sharp corners, we use a consistent `0.25rem` (4px) radius for buttons and chips to provide a modern "hardware" feel rather than a raw "software" feel.

- **Standard Elements:** 4px (Soft)
- **Large Cards/Terminals:** 10px
- **Special Elements:** Full pill shapes are reserved exclusively for status indicators and "AI Active" badges to differentiate them from functional inputs.

## Components
- **Buttons:** All-caps JetBrains Mono. Primary buttons use a solid background with a high-contrast label. Secondary/Chip buttons use an outline style. Every button must have a `:hover` glow effect.
- **Terminal Input:** Consists of a header with "Traffic Light" window controls (Magenta, Amber, Cyan) and a body featuring a persistent `~ $` prompt and a blinking block cursor.
- **Chips:** Prefixed with a `> ` character to simulate command-line arguments. Outlined with theme colors.
- **Feature Cards (Bento):** Minimalist containers with a dedicated icon slot. Icons are always framed in a square border that matches the card's accent color.
- **Navigation:** Top-docked, blurred background, with a persistent bottom border of Cyan to ground the header in the "system" aesthetic.