---
version: "alpha"
name: "Archive UI Component"
description: "Archive Playful Dashboard Section is designed for demonstrating application workflows and interface hierarchy. Key features include clear information density, modular panels, and interface rhythm. It is suitable for product showcases, admin panels, and analytics experiences."
colors:
  primary: "#9EE66E"
  secondary: "#FFD96A"
  tertiary: "#EECB69"
  neutral: "#1D1B16"
  background: "#FFFFFF"
  surface: "#FFFAF0"
  text-primary: "#1D1B16"
  text-secondary: "#7C766B"
  border: "#1D1B16"
  accent: "#9EE66E"
typography:
  display-lg:
    fontFamily: "Inter"
    fontSize: "76.44px"
    fontWeight: 500
    lineHeight: "67.2672px"
    letterSpacing: "-0.075em"
  body-md:
    fontFamily: "Inter"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "19.5px"
  label-md:
    fontFamily: "Arial"
    fontSize: "12px"
    fontWeight: 400
rounded:
  md: "100px"
spacing:
  base: "5px"
  sm: "5px"
  md: "10px"
  lg: "12px"
  xl: "13px"
  gap: "9px"
  card-padding: "11.5px"
  section-padding: "24px"
components:
  button-primary:
    backgroundColor: "{colors.background}"
    textColor: "#000000"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "10px"
  card:
    backgroundColor: "{colors.background}"
    rounded: "22px"
    padding: "26.5px"
---

## Overview

- **Composition cues:**
  - Layout: Grid
  - Content Width: Full Bleed
  - Framing: Open
  - Grid: Strong

## Colors

The color system uses light mode with #9EE66E as the main accent and #1D1B16 as the neutral foundation.

- **Primary (#9EE66E):** Main accent and emphasis color.
- **Secondary (#FFD96A):** Supporting accent for secondary emphasis.
- **Tertiary (#EECB69):** Reserved accent for supporting contrast moments.
- **Neutral (#1D1B16):** Neutral foundation for backgrounds, surfaces, and supporting chrome.

- **Usage:** Background: #FFFFFF; Surface: #FFFAF0; Text Primary: #1D1B16; Text Secondary: #7C766B; Border: #1D1B16; Accent: #9EE66E

## Typography

Typography pairs Inter for display hierarchy with Arial for supporting content and interface copy.

- **Display (`display-lg`):** Inter, 76.44px, weight 500, line-height 67.2672px, letter-spacing -0.075em.
- **Body (`body-md`):** Inter, 13px, weight 400, line-height 19.5px.
- **Labels (`label-md`):** Arial, 12px, weight 400.

## Layout

Layout follows a grid composition with reusable spacing tokens. Preserve the grid, full bleed structural frame before changing ornament or component styling. Use 5px as the base rhythm and let larger gaps step up from that cadence instead of introducing unrelated spacing values.

Treat the page as a grid / full bleed composition, and keep that framing stable when adding or remixing sections.

- **Layout type:** Grid
- **Content width:** Full Bleed
- **Base unit:** 5px
- **Scale:** 5px, 10px, 12px, 13px, 15px, 18px, 24px, 28px
- **Section padding:** 24px, 30px
- **Card padding:** 11.5px, 13.5px, 24px, 30px
- **Gaps:** 9px, 12px, 18px, 20px

## Elevation & Depth

Depth is communicated through elevated, border contrast, and reusable shadow or blur treatments. Keep those recipes consistent across hero panels, cards, and controls so the page reads as one material system.

Surfaces should read as elevated first, with borders, shadows, and blur only reinforcing that material choice.

- **Surface style:** Elevated
- **Borders:** 0.8px #1D1B16; 1.6px #FF5B4F
- **Shadows:** rgba(60, 49, 27, 0.1) 0px 18px 45px 0px; rgba(60, 49, 27, 0.12) 0px 16px 34px 0px; rgba(60, 49, 27, 0.08) 0px 24px 70px 0px

### Techniques
- **Gradient border shell:** Use a thin gradient border shell around the main card. Wrap the surface in an outer shell with 0px padding and a 36px radius. Drive the shell with none so the edge reads like premium depth instead of a flat stroke. Keep the actual stroke understated so the gradient shell remains the hero edge treatment. Inset the real content surface inside the wrapper with a slightly smaller radius so the gradient only appears as a hairline frame.

## Shapes

Shapes rely on a tight radius system anchored by 22px and scaled across cards, buttons, and supporting surfaces. Icon geometry should stay compatible with that soft-to-controlled silhouette.

Use the radius family intentionally: larger surfaces can open up, but controls and badges should stay within the same rounded DNA instead of inventing sharper or pill-only exceptions.

- **Corner radii:** 22px, 28px, 34px, 36px, 100px

## Components

Anchor interactions to the detected button styles. Reuse the existing card surface recipe for content blocks.

### Buttons
- **Primary:** background #FFFFFF, text #000000, radius 100px, padding 10px, border 0.8px solid rgba(29, 27, 22, 0.12).

### Cards and Surfaces
- **Card surface:** background #FFFFFF, border 0.8px solid rgba(29, 27, 22, 0.12), radius 22px, padding 26.5px, shadow none.
- **Card surface:** background #FFFAF0, border 0.8px solid rgba(29, 27, 22, 0.12), radius 28px, padding 30px, shadow rgba(60, 49, 27, 0.1) 0px 18px 45px 0px.
- **Card surface:** background rgba(255, 250, 240, 0.7), border 0.8px solid rgba(29, 27, 22, 0.12), radius 34px, padding 24px, shadow rgba(60, 49, 27, 0.08) 0px 24px 70px 0px.

## Do's and Don'ts

Use these constraints to keep future generations aligned with the current system instead of drifting into adjacent styles.

### Do
- Do use the primary palette as the main accent for emphasis and action states.
- Do keep spacing aligned to the detected 5px rhythm.
- Do reuse the Elevated surface treatment consistently across cards and controls.
- Do keep corner radii within the detected 22px, 28px, 34px, 36px, 100px family.

### Don't
- Don't introduce extra accent colors outside the core palette roles unless the page needs a new semantic state.
- Don't mix unrelated shadow or blur recipes that break the current depth system.
- Don't exceed the detected moderate motion intensity without a deliberate reason.

## Motion

Motion feels controlled and interface-led across text, layout, and section transitions. Timing clusters around 350ms and 650ms. Easing favors ease and cubic-bezier(0.2. Scroll choreography uses Framer Motion for section reveals and pacing.

**Motion Level:** moderate

**Durations:** 350ms, 650ms, 3500ms, 700ms

**Easings:** ease, cubic-bezier(0.2, 0.8, 0.2, 1), ease-in-out

**Scroll Patterns:** framer-motion
