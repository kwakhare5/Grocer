---
version: alpha
name: Cardboard
description: |
  Cardboard's design language is a striking study in digital minimalism meets
  creative dynamism. The system lives in a nearly-absolute darkness—pure black
  (#000000) as the default stage—punctuated by refined, serif-driven typography
  and precisely-calibrated micro-elevations. The aesthetic favors restraint:
  elegant negative space, subtle tonal shifts between black and very dark
  charcoal, and strategic pops of golden accent (#F4A825) that signal intent
  without shouting. This is a design system for a sophisticated, browser-based
  video editor aimed at creators who value control and clarity. The mood is
  assured, technical, yet approachable—typefaces oscillate between the serif
  formality of Denton for headlines and the humanist warmth of Delight for
  interface copy, creating visual rhythm that guides the eye through dense
  creative tools without cognitive overload.
source:
  url: "https://www.cardboard.ai/"
  pagesAnalyzed: 1
  extractedAt: 2026-10-25
  tokensMeasured: true
colors:
  primary: "#191919"
  accent: "#F4A825"
  canvas: "#000000"
  surface-alt: "#08090A"
  on-primary: "#D9D9D9"
  ink: "#FFFFFF"
  body: "#F0F0F0"
  muted: "#D9D9D9"
  faint: "#999999"
  hairline: "#6E9BFF"
  accent-1: "#F7C164"
  neutral-1: "#848484"
typography:
  display-xxl:
    fontFamily: Denton
    fontSize: 238px
    fontWeight: 300
    lineHeight: 0.8
    letterSpacing: 0.5px
  display-xl:
    fontFamily: Denton
    fontSize: 60px
    fontWeight: 300
    lineHeight: 0.9
    letterSpacing: 0px
  display-lg:
    fontFamily: Denton
    fontSize: 54px
    fontWeight: 300
    lineHeight: 1.02
    letterSpacing: 0px
  display-md:
    fontFamily: Denton
    fontSize: 40px
    fontWeight: 300
    lineHeight: 1.1
    letterSpacing: 0px
  display-md-loose:
    fontFamily: Denton
    fontSize: 40px
    fontWeight: 300
    lineHeight: 1.5
    letterSpacing: 0px
  display-md-tight:
    fontFamily: Denton
    fontSize: 40px
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: -0.4px
  body-xl:
    fontFamily: Delight
    fontSize: 20px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  body-lg:
    fontFamily: Delight
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0px
  body-md:
    fontFamily: Delight
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  body-sm:
    fontFamily: Delight
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0.5px
  body-sm-tight:
    fontFamily: Delight
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  body-xs:
    fontFamily: Delight
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  nav:
    fontFamily: Delight
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0.5px
  button-xl:
    fontFamily: Denton
    fontSize: 24px
    fontWeight: 300
    lineHeight: 0.94
    letterSpacing: 0px
  button-lg:
    fontFamily: Delight
    fontSize: 18px
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: 0px
  button-lg-tight:
    fontFamily: Delight
    fontSize: 18px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  button-md:
    fontFamily: Delight
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  label:
    fontFamily: Delight
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0px
  caption-md:
    fontFamily: Delight
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  caption-md-geist:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  caption-md-loose:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.58
    letterSpacing: 0px
  caption-md-strong:
    fontFamily: Delight
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0px
  caption-sm:
    fontFamily: Delight
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: 0px
  caption-xs:
    fontFamily: Geist
    fontSize: 10px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0px
rounded:
  none: 0px
  xs: 6px
  sm: 8px
  md: 10px
  lg: 12px
  xl: 20px
  full: 9999px
spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 32px
  xxxl: 40px
  section: 44px
  band: 48px
shadows:
  sm: "rgba(0, 0, 0, 0.35) 0px 12px 32px 0px"
  md: "rgba(0, 0, 0, 0.45) 2px 0px 6px 0px"
  lg: "rgba(245, 196, 81, 0.8) 0px 0px 8px 0px"
  xl: "rgba(255, 255, 255, 0.6) 0px 0px 8px 0px"
elevationStrategy: layered-micro
themes:
  derived: light   # the other theme is the site's measured palette
  light:
    bg: "#FFFCF7"
    surface: "#F5F2ED"
    surfaceRaised: "#EDEAE6"
    text: "#1C1912"
    textMuted: "#706E68"
    border: "#DBD9D4"
    accent: "#976208"
    accentFg: "#FFFFFF"
    focusRing: "#BE7C0A"
    elevation: shadow
  dark:
    bg: "#000000"
    surface: "#08090A"
    surfaceRaised: "#1C1D1E"
    text: "#FFFFFF"
    textMuted: "#F0F0F0"
    border: "#6E9BFF"
    accent: "#F4A825"
    accentFg: "#0B0B0C"
    focusRing: "#F4A825"
    elevation: "border+surface"
gradients:
  - context: hero
    kind: linear
    value: "linear-gradient(rgb(8, 9, 10) calc(100% - 200px), rgb(0, 0, 0) 100%)"
  - context: section
    kind: linear
    value: "linear-gradient(rgb(33, 33, 33), rgb(28, 28, 28)), linear-gradient(0deg, rgba(255, 255, 255, 0.08), rgba(153, 153, 153, 0.08)), linear-gradient(rgb(33, 33, 33), rgb(28, 28, 28))"
  - context: section
    kind: linear
    value: "linear-gradient(to right, rgb(8, 9, 10), rgba(8, 9, 10, 0))"
  - context: section
    kind: linear
    value: "linear-gradient(to right, rgba(8, 9, 10, 0), rgb(8, 9, 10))"
components:
  button-filled:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    height: 32.7969px
    padding: "8px 14px 8px 14px"
    rounded: "{rounded.lg}"
    backgroundColor: "rgb(33, 33, 33)"
  button-secondary:
    textColor: "{colors.canvas}"
    height: 34.2969px
    padding: "8.75px 14px 8.75px 14px"
    fontSize: 14px
    fontFamily: Delight
    fontWeight: 500
    lineHeight: 1.2
    rounded: "{rounded.lg}"
    backgroundColor: "{colors.ink}"
  button-filled-lg:
    typography: "{typography.label}"
    textColor: "{colors.ink}"
    height: 39.1875px
    padding: "10px 16px 10px 16px"
    rounded: "{rounded.lg}"
    backgroundColor: "rgb(33, 33, 33)"
  button-secondary-lg:
    typography: "{typography.label}"
    textColor: "{colors.canvas}"
    height: 39.1875px
    padding: "10px 16px 10px 16px"
    rounded: "{rounded.lg}"
    backgroundColor: "{colors.ink}"
  button-text:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    height: 28px
    padding: "0px 7px 0px 7px"
    rounded: "{rounded.sm}"
    backgroundColor: "oklab(0.999994 0.0000455678 0.0000200868 / 0.07)"
  card:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    padding: "28px 28px 28px 28px"
    rounded: "{rounded.xl}"
    backgroundColor: "rgb(17, 18, 20)"
  card-2:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    border: "1px solid rgba(110, 155, 255, 0.16)"
    padding: "28px 28px 28px 28px"
    rounded: "{rounded.xl}"
  badge-icon:
    typography: "{typography.body-sm}"
    textColor: "oklab(0.999994 0.0000455677 0.0000200868 / 0.8)"
    height: 17.5px
  navigation:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    height: 19.1875px
  footer:
    typography: "{typography.body-sm}"
    textColor: "{colors.muted}"
    padding: "70px 0px 0px 0px"
  link:
    typography: "{typography.body-sm}"
    textColor: "oklab(0.999994 0.0000455677 0.0000200868 / 0.8)"
    rounded: 9px
    backgroundColor: "oklab(0.999994 0.0000455678 0.0000200868 / 0.06)"
  link-sm:
    typography: "{typography.nav}"
    textColor: "{colors.neutral-1}"
    rounded: 5px
states:
  other-hover:
    target: other
    state: hover
    backgroundColor: "rgba(180, 180, 180, 0.7)"
breakpoints:
  - width: 375
    containerWidth: 343
    gridColumns: 2
    navLinksVisible: 0
    menuToggleVisible: true
    headingPx: 44
    bodyPx: 14
    sectionPaddingX: 16
  - width: 768
    containerWidth: 736
    gridColumns: 5
    navLinksVisible: 4
    menuToggleVisible: true
    headingPx: 60
    bodyPx: 14
    sectionPaddingX: 60
  - width: 1024
    containerWidth: 984
    gridColumns: 3
    navLinksVisible: 4
    menuToggleVisible: true
    headingPx: 60
    bodyPx: 14
    sectionPaddingX: 60
  - width: 1280
    containerWidth: 1240
    gridColumns: 4
    navLinksVisible: 4
    menuToggleVisible: true
    headingPx: 60
    bodyPx: 14
    sectionPaddingX: 60
  - width: 1440
    containerWidth: 1400
    gridColumns: 4
    navLinksVisible: 4
    menuToggleVisible: true
    headingPx: 60
    bodyPx: 14
    sectionPaddingX: 60
coverage:
  statesFound: 62
  gradientsFound: 4
  rolesUnassigned: 2
  archetypesUnnamed: 0
  archetypesDetected: 0
  responsiveMeasured: true
  stylesheetsBlocked: false
  semanticRampDeclared: false
---

# Design System Inspired by Cardboard

## 1. Visual Theme & Atmosphere

Cardboard's design language is a striking study in **digital minimalism meets creative dynamism**. The system lives in a nearly-absolute darkness—pure black (`{colors.canvas}` — `#000000`) as the default stage—punctuated by refined, serif-driven typography and precisely-calibrated micro-elevations. The aesthetic favors restraint: elegant negative space, subtle tonal shifts between black and very dark charcoal, and strategic pops of golden accent (`{colors.accent}` — `#F4A825`) that signal intent without shouting. This is a design system for a sophisticated, browser-based video editor aimed at creators who value control and clarity. The mood is **assured, technical, yet approachable**—typefaces oscillate between the serif formality of *Denton* for headlines and the humanist warmth of *Delight* for interface copy, creating visual rhythm that guides the eye through dense creative tools without cognitive overload.

**Key Characteristics**

- Nearly-black canvas with micro-tonal surface shifts (black to `#08090A`) for section zoning
- Serif display typeface (*Denton*, 300 weight) paired with humanist body font (*Delight*)
- Gold accent used sparingly for brand moments and micro-interactions
- Minimal border usage; depth conveyed via shadow and colour blocking rather than strokes
- Touch-friendly, pill-and-rounded button treatments (`{rounded.lg}` — `12px` corners)
- Layered micro-shadows for barely-perceptible elevation
- Responsive, mobile-first layout with persistent navigation structure

---

## 2. Color Palette & Roles

### Primary
- **Primary / Brand** (`{colors.primary}` — `#191919`): The core dark neutral used for CTA fills, brand accent moments, and active states. Sits between true black and the default canvas for subtle hierarchy.
- **Accent** (`{colors.accent}` — `#F4A825`): The brand's golden hue, reserved for strategic highlights, brand marks, and micro-interactions. Warm, energetic counterpoint to the achromatic palette.

### Accent Colors
- **Accent Decorative** (`{colors.accent-1}` — `#F7C164`): A lighter tint of the brand gold, treated as decorative only; no measured functional role on the site.

### Interactive
- **Hairline / Border** (`{colors.hairline}` — `#6E9BFF`): A subtle blue used for 1px borders and dividers, adding visual definition without asserting hierarchy.

### Neutral Scale
- **Canvas** (`{colors.canvas}` — `#000000`): The default page background, the system's foundational darkness.
- **Surface Alt** (`{colors.surface-alt}` — `#08090A`): A marginally lighter black used for alternating section bands and subtle depth shifts.
- **Ink / Primary Text** (`{colors.ink}` — `#FFFFFF`): Headings and primary display text, pure white for maximum contrast on dark backgrounds.
- **Body Text** (`{colors.body}` — `#F0F0F0`): Body copy and secondary text, a near-white with imperceptible warmth for reduced eye strain.
- **Muted / On Primary** (`{colors.on-primary}` — `#D9D9D9`): Captions, secondary text, and labels on brand surfaces; a mid-light grey.
- **Faint / Tertiary** (`{colors.faint}` — `#999999`): Placeholder text, disabled states, and deeply recessive elements.
- **Neutral Secondary** (`{colors.neutral-1}` — `#848484`): A neutral grey with no measured functional role; treat as decorative.

---

## 3. Typography Rules

### Font Family

**Display & Headlines:** *Denton* (serif, 300 weight regular)
- Fallback stack: Georgia, serif

**Body & Interface:** *Delight* (humanist sans, 400–500 weight)
- Fallback stack: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif

**Captions & Technical:** *Geist* (monospace-influenced, 400 weight)
- Fallback stack: "Courier New", monospace

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|---|---|---|---|---|---|---|
| Display XXL | Denton | 238px | 300 | 0.8 | 0.5px | Ultra-large hero display; extreme tracking tightness |
| Display LG | Denton | 54px | 300 | 1.02 | 0px | Section hero headlines |
| Display XL | Denton | 60px | 300 | 0.9 | 0px | Main page heading; tight line spacing for impact |
| Display MD | Denton | 40px | 300 | 1.1 | 0px | Section subheadings; multiple line-height variants for layout flexibility |
| Display MD (Loose) | Denton | 40px | 300 | 1.5 | 0px | Display-weight copy with generous leading |
| Display MD (Tight) | Denton | 40px | 300 | 1.2 | −0.4px | Compressed variant with negative tracking |
| Button XL | Denton | 24px | 300 | 0.94 | 0px | Large button text; serif treatment for premium feel |
| Label | Delight | 16px | 500 | 1.2 | 0px | Form labels and input headers |
| Body LG | Delight | 16px | 500 | 1.5 | 0px | Lead paragraphs and emphasized body copy |
| Body XL | Delight | 20px | 500 | 1.4 | 0px | Larger body paragraphs; prominent interface text |
| Body MD | Delight | 15px | 400 | 1.4 | 0px | Standard body copy |
| Body SM | Delight | 14px | 400 | 1.5 | 0.5px | Secondary copy; extended tracking for legibility at smaller sizes |
| Body SM (Tight) | Delight | 14px | 400 | 1.4 | 0px | Compact body variant |
| Body XS | Delight | 13px | 400 | 1.4 | 0px | Tertiary body text |
| Button LG | Delight | 18px | 500 | 1.45 | 0px | Large button labels |
| Button LG (Tight) | Delight | 18px | 500 | 1.4 | 0px | Compressed button variant |
| Button MD | Delight | 14px | 400 | 1.5 | 0px | Standard button text |
| Caption MD | Delight | 12px | 400 | 1.4 | 0px | Captions and fine print |
| Caption MD (Strong) | Delight | 12px | 500 | 1.4 | 0px | Emphasized caption |
| Caption MD (Geist) | Geist | 12px | 400 | 1.5 | 0px | Technical captions in monospace voice |
| Caption MD (Loose) | Geist | 12px | 400 | 1.58 | 0px | Spacious caption variant |
| Caption SM | Delight | 11px | 500 | 1.3 | 0px | Smallest caption size |
| Caption XS | Geist | 10px | 400 | 1.2 | 0px | Micro-text and footnotes |
| Nav Link | Delight | 16px | 400 | 1.2 | 0.5px | Navigation text; extended tracking for clarity |

### Principles

- **Serif for Presence:** *Denton* at 300 weight creates a sophisticated, contemporary voice for display. Negative tracking on the largest sizes (e.g., `{typography.display-md-tight}` at −0.4px) compresses the visual texture, reinforcing emphasis.
- **Humanist Sans for Warmth:** *Delight* humanizes the interface, avoiding the coldness of geometric fonts. Mid-weights (400–500) balance friendliness with clarity.
- **Tracking as Rhythm:** Letter-spacing is intentional—extended on body copy and navigation for breath, tightened on large display for gravitas.
- **Line Height for Scanning:** Generous line-heights (1.4–1.5) on body copy ensure readability on screens; tighter ratios (0.8–0.9) on display sizes compound the dramatic effect.

---

## 4. Component Stylings

### Buttons

**Primary Filled (MD)**
- **Background:** `rgb(33, 33, 33)` (nearly-black, darker than canvas for active state)
- **Text Color:** `rgb(217, 217, 217)` ({colors.on-primary})
- **Padding:** `8px 14px`
- **Font:** {typography.button-md} (Delight, 14px, 400, line-height 1.5)
- **Border Radius:** {rounded.lg} (12px)
- **Border:** None
- **Box Shadow:** None
- **Width:** 130px (compact button)
- **Interaction:** On `:hover`, backgroundColor shifts to `rgba(255, 255, 255, 0.15)` (subtle lift) or context-specific brand accents

**Secondary (MD)** — Light Background
- **Background:** `rgb(255, 255, 255)` ({colors.ink})
- **Text Color:** `rgb(0, 0, 0)` (inverted for contrast)
- **Padding:** `8.75px 14px`
- **Font:** {typography.button-md} (Delight, 14px, 500, line-height 1.4)
- **Border Radius:** {rounded.lg} (12px)
- **Border:** None
- **Box Shadow:** None
- **Width:** 118.5px

**Primary Filled (LG)**
- **Background:** `rgb(33, 33, 33)`
- **Text Color:** `rgb(255, 255, 255)` (white for large CTAs)
- **Padding:** `10px 16px`
- **Font:** {typography.button-lg} (Delight, 18px, 500, line-height 1.45)
- **Border Radius:** {rounded.lg} (12px)
- **Border:** None
- **Box Shadow:** None
- **Width:** 272px
- **Interaction:** Responds to hover with elevated backgrounds or brand accent highlights

**Secondary (LG)** — Light Background
- **Background:** `rgb(255, 255, 255)`
- **Text Color:** `rgb(0, 0, 0)`
- **Padding:** `10px 16px`
- **Font:** {typography.button-lg} (Delight, 18px, 500, line-height 1.45)
- **Border Radius:** {rounded.lg} (12px)
- **Border:** None
- **Box Shadow:** None
- **Width:** 270px

**Text Button (Icon)**
- **Background:** `oklab(0.999994 0.0000455678 0.0000200868 / 0.07)` (near-transparent white at 7% opacity)
- **Text Color:** `rgb(217, 217, 217)`
- **Padding:** `0px 7px`
- **Font:** {typography.button-md} (Delight, 14px, 400, line-height 1.5)
- **Border Radius:** {rounded.sm} (8px)
- **Border:** None
- **Box Shadow:** None
- **Width / Height:** 28px (square icon button)
- **Interaction:** Background opacity increases on hover

### Cards & Containers

**Card Default (Filled)**
- **Background:** `rgb(17, 18, 20)` (very dark grey, surface color)
- **Text Color:** `rgb(217, 217, 217)` ({colors.on-primary})
- **Padding:** `28px`
- **Font:** {typography.body-md} (Delight, 15px, 400, line-height 1.4)
- **Border Radius:** {rounded.xl} (20px)
- **Border:** None
- **Box Shadow:** None
- **Width / Height:** 328px / 698px (measured on product card)

**Card Default (Outlined / Bordered)**
- **Background:** `rgba(0, 0, 0, 0)` (transparent)
- **Text Color:** `rgb(217, 217, 217)`
- **Padding:** `28px`
- **Font:** {typography.body-md}
- **Border Radius:** {rounded.xl} (20px)
- **Border:** `1px solid rgba(110, 155, 255, 0.16)` (hairline with subtle blue tint, 16% opacity)
- **Box Shadow:** None
- **Interaction:** Border brightens on hover to higher opacity or shifts to accent colors

### Inputs & Forms

**Input / Label Text**
- **Font:** {typography.label} (Delight, 16px, 500, line-height 1.2)
- **Text Color:** {colors.on-primary} (`#D9D9D9`)
- **Border Radius:** `0px` (sharp, no rounding on inputs in this system)
- **Background:** Typically {colors.surface-alt} or transparent, depending on state
- **Interaction:** Borders respond to focus with accent color or increased opacity

### Navigation

**Nav Link (Default)**
- **Font:** {typography.nav} (Delight, 16px, 400, line-height 1.2, letter-spacing 0.5px)
- **Text Color:** `rgb(217, 217, 217)` ({colors.on-primary})
- **Border Radius:** `0px` (no rounding)
- **Background:** Transparent
- **Padding:** `0px` (text-only links)
- **Interaction:** Text color shifts to {colors.ink} or accent on hover/active

**Nav Link (Small Secondary)**
- **Font:** Delight, 16px, 400, line-height 1.2
- **Text Color:** `rgb(132, 132, 132)` ({colors.neutral-1})
- **Border Radius:** `5px`
- **Background:** Transparent
- **Padding:** `0px`
- **Interaction:** Color lightens or accent applied on hover

### Badge

**Icon Badge**
- **Background:** Transparent
- **Text / Icon Color:** `oklab(0.999994 0.0000455677 0.0000200868 / 0.8)` (white at 80% opacity)
- **Border Radius:** `0px` (sharp)
- **Padding:** `0px`
- **Font Size:** 14px
- **Width / Height:** 17.5px (small indicator)

### Link

**Link (Default)**
- **Font:** {typography.body-sm} (Delight, 14px, 400, line-height 1.5, letter-spacing 0.5px)
- **Text Color:** `oklab(0.999994 0.0000455677 0.0000200868 / 0.8)` (near-white)
- **Background:** `oklab(0.999994 0.0000455678 0.0000200868 / 0.06)` (white at 6% opacity, subtle hover state)
- **Border Radius:** `9px`
- **Padding:** `0px`
- **Interaction:** Background opacity increases on hover

**Link (Small Secondary)**
- **Font:** Delight, 16px, 400, line-height 1.2
- **Text Color:** `rgb(132, 132, 132)`
- **Background:** Transparent
- **Border Radius:** `5px`
- **Padding:** `0px`

---

## 5. Layout Principles

### Spacing System

The spacing scale uses a **base unit of 4px**, doubling or scaling multiplicatively across sizes. This allows both tight microspacing and generous section breaks.

| Token | Value | Context |
|---|---|---|
| {spacing.xxs} | 4px | Inline micro-spacing between adjacent elements |
| {spacing.xs} | 8px | Compact padding in small components (badges, icon buttons) |
| {spacing.sm} | 12px | Padding in medium buttons and form inputs |
| {spacing.md} | 16px | Standard component padding; horizontal gutters in narrow viewports |
| {spacing.lg} | 20px | Breathing room between section blocks |
| {spacing.xl} | 24px | Card and container internal padding |
| {spacing.xxl} | 32px | Large section spacing |
| {spacing.section} | 44px | Vertical spacing between distinct content sections |
| {spacing.band} | 48px | Large band / hero section padding; major layout breaks |

### Grid & Container

| Viewport | Container Width | Section Padding-X | Grid Columns | Notes |
|---|---|---|---|---|
| 375px | 343px | 16px | 2 | Mobile; tight margins, minimal columns for readable text wrapping |
| 768px | 736px | 60px | 5 | Tablet; expanded padding and columns begin to show |
| 1024px | 984px | 60px | 3 | Small desktop; settling into comfortable multi-column layouts |
| 1280px | 1240px | 60px | 4 | Standard desktop; column count stabilizes |
| 1440px | 1400px | 60px | 4 | Large desktop; same column structure with extra whitespace |

- **Max Container Width:** 1400px (at 1440px viewport)
- **Grid Strategy:** Flexible column counts based on viewport; horizontal padding remains generous at tablet and above (60px) to frame content elegantly
- **Section Pattern:** Full-width sections with alternating `{colors.canvas}` and `{colors.surface-alt}` backgrounds create visual rhythm. Inner content is constrained to max-width containers with symmetric side padding.

### Whitespace Philosophy

Cardboard embraces **generous negative space** as a core aesthetic principle. The deep black canvas absorbs visual weight, allowing typography and interactive elements to float with clarity. Section padding is consistent and predictable—`{spacing.band}` (48px) between major content zones ensures breathing room without feeling loose. Card padding is uniform at `{spacing.xl}` (24px), fostering a sense of considered craft. This spacing language prevents interface clutter and reinforces the brand's sophisticated, focused positioning.

### Border Radius Scale

The system employs a consistent rounding strategy across interactive and container components:

| Token | Value | Components |
|---|---|---|
| {rounded.none} | 0px | Images, badges, inputs (sharp, technical aesthetic) |
| {rounded.xs} | 6px | Micro-interactions, small badges |
| {rounded.sm} | 8px | Icon buttons, compact inputs |
| {rounded.md} | 10px | Medium interactive elements |
| {rounded.lg} | 12px | **Primary button and card treatment**; the system's signature rounded look |
| {rounded.xl} | 20px | **Large cards and prominent containers**; creates warmth and approachability |
| {rounded.full} | 9999px | Pill-shaped buttons and toggles (when used) |

The prevalence of `{rounded.lg}` (12px) and `{rounded.xl}` (20px) on buttons and cards gives Cardboard a **friendly, modern-minimalist character** —rounded enough to feel contemporary, not so rounded as to become cartoonish.

---

## 6. Depth & Elevation

Cardboard uses **layered micro-shadows** rather than bold depth shifts. The system favors barely-perceptible lifts, achieved through stacked, near-transparent layers and subtle color blocking.

| Level | Treatment | Use |
|---|---|---|
| Flat | No shadow | Default cards, buttons, and background surfaces |
| Micro (SM) | `rgba(0, 0, 0, 0.35) 0px 12px 32px 0px` | Subtle lift on hover; floating elements like tooltips or modals |
| Micro (MD) | `rgba(0, 0, 0, 0.45) 2px 0px 6px 0px` | Directional shadow (offset-y minimal, offset-x 2px); used on dropdown menus and overlays |
| Accent (LG) | `rgba(245, 196, 81, 0.8) 0px 0px 8px 0px` | Warm glow; rare highlight for brand-accent interactive moments (e.g., focused brand buttons) |
| Accent (XL) | `rgba(255, 255, 255, 0.6) 0px 0px 8px 0px` | Cool halo; rare use on prominent white or light-colored elements for ethereal lift |

**Shadow Philosophy:** Rather than a traditional tiered shadow system (sm/md/lg creating progressively deeper lifts), Cardboard employs **color-modulated shadows** that echo the component or context. Most interactions use the dark, soft shadows (SM/MD) to maintain visual restraint. Accent shadows (LG/XL) are reserved for brand moments or high-emphasis states, adding personality without disrupting the minimalist foundation.

### Opacity Levels

The system reserves specific opacity values for semantic and interactive moments:

| Opacity | Use Case |
|---|---|
| 6% | Subtle background highlights on links and ghost buttons |
| 7% | Extremely faint background; barely-there hover states |
| 8% | Light hover state for interactive elements |
| 10% | Elevated faint background; increased discoverability |
| 14–16% | Moderate border tints and semi-transparent overlays |
| 40–45% | Strong hover or active backgrounds; high contrast |
| 50% | Overlay or scrim backgrounds; modal transitions |
| 60% | Semi-transparent text or icons; reduced emphasis |
| 80% | High-visibility secondary elements; icon colors |
| 90% | Near-solid secondary content |

### Z-index / Layering

The stacking order is minimal and explicit:

| Layer | Z-Index | Use |
|---|---|---|
| Base | 1 | Default page content |
| Raised | 2 | Slightly elevated cards or sections |
| Dropdown | 10 | Menus and select overlays |
| Sticky / Fixed | 20 | Sticky headers, fixed sidebars |
| Modal / Dialog | 50 | Overlays, modals, critical interactions |

This shallow stacking order reflects the system's minimalist philosophy—rarely are elements layered beyond the modal level, preserving visual clarity and preventing the "stack overflow" effect of over-indexed design systems.

---

## 7. Do's and Don'ts

### Do

- **Use the serif typeface (*Denton*) for headlines and display-size text.** Its 300 weight and elegant proportions communicate sophistication and draw the eye. Pair with tight line heights (0.8–1.1) for impact.
- **Maintain generous padding and whitespace** around content. The dark background absorbs visual weight; negative space is your ally.
- **Apply the golden accent (`{colors.accent}` — `#F4A825`) sparingly** for CTAs, brand moments, and micro-interactions. Overuse dulls its impact.
- **Use `{rounded.lg}` (12px) or `{rounded.xl}` (20px) on interactive components and cards.** This is the system's signature rounded aesthetic.
- **Layer micro-shadows subtly.** The system relies on barely-perceptible lifts and color blocking, not dramatic elevation.
- **Keep inputs, badges, and technical elements sharp** (`0px` border radius) to maintain a clean, modern technical edge.
- **Extend letter-spacing on navigation and body copy** at small sizes (14px and below) for improved legibility and rhythm.
- **Use `{colors.on-primary}` (`#D9D9D9`) for secondary text** on dark backgrounds; it is readable and sophisticated without the harshness of pure white.
- **Ensure touch targets are at least 44px tall or wide** on mobile; the system's humanist sans-serif is friendly and accessible when affordances are clear.

### Don't

- **Don't use *Denton* (serif) for body copy or interface labels.** It is a display typeface; *Delight* (sans) is the workhorse.
- **Don't add borders to every element.** Cardboard achieves hierarchy through color blocking and shadow, not outline proliferation. Use `{colors.hairline}` (`#6E9BFF`) sparingly for subtle divisions.
- **Don't invert text on dark backgrounds without sufficient contrast.** {colors.body} (`#F0F0F0`) and {colors.on-primary} (`#D9D9D9`) are intentional mid-tones; avoid pure white on `{colors.canvas}` unless it is a heading or CTA.
- **Don't use the brand accent as a background fill for large areas.** It is a highlight colour, not a primary surface. Reserve it for buttons, badges, and micro-interactions.
- **Don't over-round corners on technical elements.** Inputs, badges, and icon buttons often measure `0px` or `{rounded.sm}` (8px) to reinforce a precise, tool-like quality.
- **Don't layer more than 3–4 visual elements vertically without section breaks.** The {spacing.section} (44px) and {spacing.band} (48px) scales exist to prevent visual fatigue.
- **Don't add drop shadows to large sections or cards unless they are modals or floating layers.** The system is minimalist; let background colour and structure convey depth.
- **Don't stretch text to extreme widths on desktop.** The 1400px max-width container and the 60px side padding ensure comfortable reading line lengths.

---

## 8. Responsive Behavior

### Breakpoints

| Breakpoint | Viewport Width | Container Width | Section Padding-X | Grid Columns | Key Changes |
|---|---|---|---|---|---|
| Mobile | 375px | 343px | 16px | 2 | Single/dual-column layouts; hamburger menu appears; headings compress to 44px |
| Tablet | 768px | 736px | 60px | 5 | Headings expand to 60px; 4 nav links visible; layout gains columns and breathing room |
| Small Desktop | 1024px | 984px | 60px | 3 | Stable multi-column grid; full navigation visible; major sections take defined shapes |
| Desktop | 1280px | 1240px | 60px | 4 | Refined column structure; hero sections fully composed; no further major shifts |
| Large Desktop | 1440px | 1400px | 60px | 4 | Max-width container reached; extra horizontal space absorbed as outer margin |

**Transition Logic:**
- At mobile (375px), the navigation collapses behind a menu toggle; only hamburger icon visible.
- Between 375px and 768px, gradual expand: padding increases, typography remains at mobile sizes (44px display headings).
- At 768px, headings jump to 60px, and 4 nav links appear in the header (hamburger still present for backwards compatibility).
- At 1024px+, full multi-column layouts stabilize; no further navigation changes.
- At 1440px+, container max-width caps content; outer margins grow to fill the viewport.

### Touch Targets

- **Minimum button height:** 44px (measured on primary buttons; some icon buttons compress to 32–40px)
- **Minimum button width:** 44px (square icon buttons) or proportional width for text buttons
- **Link / tap area:** 28–32px minimum for icon buttons; text links inherit from typography but should have at least 36–44px padding around them
- **Form input height:** 36–40px (measured inputs show 34–39px; add padding to reach 44px if needed)
- **Spacing between interactive elements:** At least {spacing.md} (16px) to prevent accidental taps

On mobile (<768px), ensure all interactive elements are comfortably sized; buttons typically expand to full-width or near-full-width stacks to maximize tap-ability.

### Collapsing Strategy

1. **Navigation:** Transitions from inline links (4 visible at 768px+) to hamburger menu toggle at mobile. Menu likely slides in from left or appears as an overlay.
2. **Hero Sections:** Display heading size (`{typography.display-xl}` — 60px) remains constant above 768px; may compress to `{typography.display-md}` (40px) on mobile, but extraction did not measure this. Assume 44px on very small screens based on observed mobile heading.
3. **Multi-Column Layouts:** At 375px, grids collapse to 2 columns or single column. At 768px+, expand to 3–5 columns. Cards maintain fixed width (328px) until viewport can fit 2+ cards; then stack vertically on mobile.
4. **Padding & Margins:** Section padding-x shifts from {spacing.md} (16px) at 375px to {spacing.section} (44px) at 768px, settling at 60px on larger screens. Vertical spacing ({spacing.band} — 48px, {spacing.section} — 44px) remains consistent.
5. **Images & Media:** Full-width at mobile (constrained to container-width minus side padding), scaled proportionally on desktop with max-width container enforced.
6. **Forms & Inputs:** Typically full-width on mobile, constrained to column widths or max-widths on desktop.

---

## 9. Agent Prompt Guide

### Quick Color Reference

- **Primary CTA / Brand Accent:** Accent (`#F4A825`) — golden, reserved for high-signal moments
- **Primary Button Fill:** Primary (`#191919`) — dark neutral for filled CTAs
- **Page Background:** Canvas (`#000000`) — pure black, foundational
- **Section Alt Band:** Surface Alt (`#08090A`) — marginally lighter for visual separation
- **Heading Text:** Ink (`#FFFFFF`) — pure white for maximum contrast
- **Body Text:** Body (`#F0F0F0`) — near-white, reduced glare
- **Secondary / Muted Text:** On Primary (`#D9D9D9`) — mid-light grey for reduced emphasis
- **Tertiary / Placeholder:** Faint (`#999999`) — deeply recessive
- **Borders / Dividers:** Hairline (`#6E9BFF`) — subtle blue tint for structure
- **Decorative Accent (Secondary):** Accent 1 (`#F7C164`) — lighter gold; no measured role; use sparingly

### Iteration Guide

1. **Typography is serif + sans:** Use *Denton* (300 weight) for all display text (display-lg through display-xxl, button-xl). Use *Delight* (400–500) for body, nav, buttons (button-md through button-lg), and forms. Track letter-spacing exactly as specified; negative tracking on large displays (e.g., −0.4px on display-md-tight) is intentional and brand-defining.

2. **Spacing is 4px-based:** All padding, margins, and gaps should snap to the scale (4px, 8px, 12px, 16px, 20px, 24px, 32px, 44px, 48px). Section breaks use {spacing.band} (48px) or {spacing.section} (44px); component internals use {spacing.xl} (24px) for cards, {spacing.md} (16px) for standard gutters.

3. **Buttons and cards are consistently rounded:** Buttons and cards use {rounded.lg} (12px) or {rounded.xl} (20px). Inputs, badges, and technical elements are sharp (0px) or lightly rounded ({rounded.sm} — 8px). No button in the system is fully rounded (pill-shaped) unless explicitly marked.

4. **Depth is micro and colour-modulated:** Shadows are barely perceptible (SM: 0px 12px 32px with 35% black opacity; MD: 2px 0px 6px with 45% black opacity). Avoid large, obvious drop shadows. For brand moments, use colour-tinted shadows (golden for accent moments, cool white for ethereal lifts). Most interactive elements simply shift background colour or opacity on hover, not shadow.

5. **Dark background drives hierarchy:** Canvas (`#000000`) is the default; alternating `{colors.surface-alt}` (`#08090A`) sections add zoning. Elevation is achieved through color shifts, not shadow proliferation. Use {colors.on-primary} (`#D9D9D9`) and {colors.faint} (`#999999`) to reduce emphasis; pure white ({colors.ink}) only for headings or the most prominent CTAs.

6. **Accent is rare and purposeful:** The golden accent (`#F4A825`) appears on brand marks, key CTAs, and micro-interactions. Use it 2–3 times per page maximum. Avoid accent backgrounds for large content areas; it is a highlight, not a primary surface.

7. **Responsive collapse is predictable:** Mobile (375px) uses 16px side padding, 2-column grids, and hamburger menu. Tablet (768px) introduces 4 nav links, 60px side padding, and 5-column grids. Desktop (1024px+) stabilizes at 3–4 columns, 60px padding, and full navigation. Headings remain 44px on mobile; jump to 60px at 768px. Max container width is 1400px (at 1440px viewport).

8. **Touch targets and forms matter:** Buttons are at least 44px tall; icon buttons may compress to 32px but should be padded for easier tapping. Forms use sharp inputs (0px radius) unless explicitly rounded. Links and nav items receive generous padding for mobile usability. All text is readable at 14px+ on mobile viewports.

9. **Opacity layers convey state:** Use opacity scales (6–90%) to show hover/active/disabled states rather than inventing new colors. Borders tint to `rgba(110, 155, 255, 0.16)` for subtle definition; backgrounds lighten or darken at 7–16% opacity for feedback. Never apply opacity below 6% for interactive feedback.

10. **z-index is shallow:** Base layers are 1–2, dropdowns 10–20, modals 50. Rarely exceed z-index 50. The system avoids over-indexed stacking, maintaining visual clarity and preventing modal-hell complexity.

---

## 10. Known Gaps

- **Semantic Color Ramp:** The site does not expose error, success, or warning colors in its measured styles. No status ramp is documented; do not invent one. If error or validation states appear in the live product, they are not evident in this extraction.

- **Interaction States on Buttons & Links:** The extraction captured some `:hover` states (e.g., background opacity shifts, border color transitions), but not all possible states. Specifically:
  - `:focus` state data is minimal (one `:focus` color entry captured).
  - `:active` (pressed) states are not explicitly measured.
  - `:disabled` states are not documented.
  - `:focus-visible` (keyboard navigation) is unmeasured.
  
  Assume hover states increase opacity or shift to accent colors; infer active/disabled states from the scale provided, but confirm with live testing.

- **Dark/Light Mode:** Only one theme was extracted (dark background throughout). No light-mode variant was measured. The site may ship a light theme; this document describes the measured dark version only.

- **Two Colors Without Measured Role:** {colors.accent-1} (`#F7C164`) and {colors.neutral-1} (`#848484`) have no documented functional role in the system. Treat them as decorative or complementary tints; do not assign semantic meaning without further confirmation.

- **Component States & Variants:** Only static component snapshots were captured. Loading states, skeleton screens, error overlays, and other dynamic UI patterns are not documented. Assume standard patterns (opacity, placeholder backgrounds) unless the live site contradicts.

- **Animation & Motion:** No timing, easing, or animation keyframes were extracted. Interaction motion (transitions, hover animations, scroll triggers) is unmeasured. Assume subtle, fast transitions (200–300ms, ease-in-out) align with the minimalist aesthetic, but confirm with live testing.

- **Surfaces Behind Authentication:** The site may have logged-in or premium surfaces, forms, or workflows. This extraction covers only the public marketing homepage and landing page. Editor UI, user dashboards, or authenticated features are not measured.

- **Breakpoint Below 375px:** No viewport narrower than 375px was measured. If the site supports very small mobile devices (<320px width), layout behavior at those sizes is unknown. Assume graceful degradation or that such viewports are out of scope.

- **Responsive Typography:** Only one heading size per breakpoint was measured. Intermediate sizes (e.g., h4, h5, h6) or responsive adjustments within a breakpoint are not documented. Assume the primary heading size is representative; test other typographic roles on device to confirm scaling.

- **Advanced Form Elements:** Rich form components (date pickers, multi-select dropdowns, toggles, radio buttons) were not captured. Only simple inputs and basic buttons are documented. Extend the rounded and spacing principles to complex form elements, but verify styling on implementation.

- **Gradients & Decorative Layers:** Several gradient overrides were captured (hero, section bands) and are reproducible as written. However, additional decorative gradients, textures, or background images on specific sections may exist but were not fully indexed. Reproduce the captured gradients exactly; infer others from context (e.g., overlays, scrim backgrounds).

---

**Document Version:** 1.0  
**Last Updated:** Based on Cardboard public marketing homepage extraction  
**Coverage:** 1 page analysed; authenticated and premium features not visited  
**Confidence:** High for measured components and established tokens; medium for inferred interaction states and responsive tweaks not explicitly captured.