---
version: alpha
name: Gumloop
description: |
  Gumloop's design system embodies a modern, technology-forward aesthetic built
  for serious enterprise AI work. The visual language combines crisp, minimalist
  surfaces with vibrant accent colors that signal interactivity and brand
  presence. Clean typography, ample whitespace, and a deliberately restrained
  color palette create an air of professionalism and precision. The system
  avoids unnecessary ornamentation—every element serves a function. Accent
  colors (particularly the brand blue) punctuate the interface with energy,
  while neutral grays and blacks maintain clarity and hierarchy. The overall
  effect is sophisticated, approachable, and designed to inspire confidence in
  complex AI agent workflows.
source:
  url: "https://www.gumloop.com/"
  pagesAnalyzed: 1
  extractedAt: 2026-11-04
  tokensMeasured: true
colors:
  primary: "#1E8CFF"
  accent: "#522A10"
  canvas: "#FFFFFF"
  on-primary: "#FFFFFF"
  accent-1: "#1C1A19"
  accent-2: "#190D30"
  accent-3: "#147BD1"
  accent-4: "#8922EE"
  accent-5: "#5B5FC7"
  accent-6: "#95BF47"
  neutral-1: "#000000"
typography:
  display:
    fontFamily: Gellix
    fontSize: 48px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: -1.2px
  heading-md:
    fontFamily: Gellix
    fontSize: 36px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: -0.9px
  heading-sm:
    fontFamily: Gellix
    fontSize: 20px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: 0px
  quote:
    fontFamily: Gellix
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0px
  body-xl:
    fontFamily: Gellix
    fontSize: 24px
    fontWeight: 500
    lineHeight: 1.33
    letterSpacing: 0px
  body-lg:
    fontFamily: Gellix
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0px
  body-md:
    fontFamily: GeistSans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: 0px
  body-md-loose:
    fontFamily: GeistSans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0px
  body-md-2:
    fontFamily: GeistSans
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  body-sm:
    fontFamily: GeistSans
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.38
    letterSpacing: 0px
  nav:
    fontFamily: GeistSans
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.43
    letterSpacing: 0px
  button-lg:
    fontFamily: GeistSans
    fontSize: 18px
    fontWeight: 500
    lineHeight: 1.56
    letterSpacing: 0px
  button-md:
    fontFamily: GeistSans
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  button-sm:
    fontFamily: GeistSans
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0px
  button-xs:
    fontFamily: GeistSans
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.38
    letterSpacing: 0px
  caption-md:
    fontFamily: GeistSans
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.33
    letterSpacing: 0px
  caption-md-strong:
    fontFamily: GeistSans
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.33
    letterSpacing: 0px
  caption-sm:
    fontFamily: GeistSans
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  caption-sm-strong:
    fontFamily: GeistSans
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0px
  caption-xs:
    fontFamily: GeistSans
    fontSize: 10px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  caption-xs-strong:
    fontFamily: GeistSans
    fontSize: 10px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0px
  code:
    fontFamily: GeistMono
    fontSize: 60px
    fontWeight: 300
    lineHeight: 1
    letterSpacing: 0px
rounded:
  none: 0px
  xs: 2px
  sm: 6px
  md: 8px
  lg: 10px
  xl: 12px
  full: 9999px
spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 28px
  xxxl: 32px
  section: 40px
  band: 48px
borderWidths:
  thin: 1px
shadows:
  sm: "lab(90.0141 0.811607 -2.9353) 0px 0px 0px 1px, rgba(0, 0, 0, 0.05) 0px 1px 1px -0.5px, rgba(0, 0, 0, 0.05) 0px 3px 3px -1.5px, rgba(0, 0, 0, 0.04) 0px 6px 6px -3px, rgba(0, 0, 0, 0.04) 0px 12px 12px -6px, rgba(0, 0, 0, 0.04) 0px 24px 24px -12px"
elevationStrategy: single-tier
themes:
  derived: dark   # the other theme is the site's measured palette
  light:
    bg: "#FFFFFF"
    surface: "#F7F7F7"
    surfaceRaised: "#EEEEEE"
    text: "#111111"
    textMuted: "#646464"
    border: "#E2E2E2"
    accent: "#1E8CFF"
    accentFg: "#000000"
    focusRing: "#1E8CFF"
    elevation: shadow
  dark:
    bg: "#090F15"
    surface: "#181D23"
    surfaceRaised: "#24292F"
    text: "#F6FAFF"
    textMuted: "#9CA1A6"
    border: "#30353A"
    accent: "#1E8CFF"
    accentFg: "#0B0B0C"
    focusRing: "#1E8CFF"
    elevation: "border+surface"
gradients:
  - context: section
    kind: linear
    value: "linear-gradient(oklab(0.750006 0.102492 0.151603 / 0.5) 0%, oklab(0.750006 0.102492 0.151603 / 0.3) 100%)"
    filter: "blur(12px)"
  - context: section
    kind: linear
    value: "linear-gradient(oklab(0.710004 0.214912 -0.0290765 / 0.5) 0%, oklab(0.710004 0.214912 -0.0290765 / 0.3) 100%)"
    filter: "blur(12px)"
  - context: section
    kind: linear
    value: "linear-gradient(oklab(0.829993 -0.102084 -0.0814393 / 0.5) 0%, oklab(0.829993 -0.102084 -0.0814393 / 0.3) 100%)"
    filter: "blur(12px)"
components:
  button-primary:
    typography: "{typography.button-md}"
    textColor: "{colors.on-primary}"
    height: 59.9763px
    padding: "8px 10px 8px 10px"
    rounded: "{rounded.lg}"
    backgroundColor: "{colors.primary}"
  button-text:
    typography: "{typography.nav}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 28px
    padding: "8px 8px 8px 8px"
    rounded: "{rounded.md}"
    backgroundColor: "oklab(0.964998 0.00111422 -0.00381607 / 0.45)"
  button-text-lg:
    typography: "{typography.nav}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 36px
    padding: "8px 18px 8px 18px"
    boxShadow: "rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, lab(90.0141 0.811607 -2.9353) 0px 0px 0px 1px, rgba(0, 0, 0, 0.016) 0px 1px 1px -0.5px, rgba(0, 0, 0, 0.016) 0px 3px 3px -1.5px, rgba(0, 0, 0, 0.01) 0px 6px 6px -3px, rgba(0, 0, 0, 0.01) 0px 12px 12px -6px, rgba(0, 0, 0, 0.01) 0px 24px 24px -12px"
    rounded: "{rounded.md}"
    backgroundColor: "lab(100 0 0)"
  button-filled:
    typography: "{typography.nav}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 44px
    padding: "12px 20px 12px 20px"
    rounded: "{rounded.lg}"
    backgroundColor: "rgb(194, 231, 255)"
  card:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    border: "1px solid lab(100 0 0 / 0.14)"
    rounded: "{rounded.md}"
    backgroundColor: "lab(100 0 0 / 0.05)"
  card-lg:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    backgroundColor: "lab(100 0 0)"
  badge-text:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 44px
    rounded: 32px
    backgroundColor: "lab(100 0 0)"
  badge-text-2:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 44px
    padding: "10px 16px 10px 16px"
  navigation:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    height: 53px
  footer:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    padding: "40px 0px 40px 0px"
    backgroundColor: "{colors.canvas}"
  link:
    typography: "{typography.button-md}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    border: "1px solid lab(93.2622 0.8111 -2.93562)"
    padding: "0px 24px 0px 24px"
    rounded: "{rounded.sm}"
    backgroundColor: "lab(95.9053 0.399023 -1.45465)"
  link-2:
    typography: "{typography.nav}"
    textColor: "lab(8.70976 -0.096187 -1.58296)"
    padding: "6px 8px 6px 8px"
states:
  other-focus-visible:
    target: other
    state: focus-visible
    outline: none
  input-focus:
    target: input
    state: focus
    outline: "rgba(0, 0, 0, 0) solid 2px"
    outlineColor: "rgba(0, 0, 0, 0)"
    outlineWidth: 2px
  other-focus:
    target: other
    state: focus
    outline: "rgba(0, 0, 0, 0) solid 2px"
    outlineColor: "rgba(0, 0, 0, 0)"
    outlineWidth: 2px
  other-hover:
    target: other
    state: hover
    borderColor: "rgba(0, 0, 0, 0)"
    backgroundColor: currentcolor
  badge-hover:
    target: badge
    state: hover
    opacity: 0
  link-hover:
    target: link
    state: hover
    opacity: 1
  button-hover:
    target: button
    state: hover
    opacity: 0
  nav-hover:
    target: nav
    state: hover
    opacity: 1
  input-hover:
    target: input
    state: hover
    opacity: 0
breakpoints:
  - width: 375
    containerWidth: 343
    gridColumns: 4
    navLinksVisible: 1
    menuToggleVisible: true
    headingPx: 36
    bodyPx: 16
    sectionPaddingX: 0
  - width: 768
    containerWidth: 736
    gridColumns: 4
    navLinksVisible: 1
    menuToggleVisible: true
    headingPx: 48
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1024
    containerWidth: 992
    gridColumns: 5
    navLinksVisible: 6
    menuToggleVisible: true
    headingPx: 48
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1280
    containerWidth: 1200
    gridColumns: 5
    navLinksVisible: 6
    menuToggleVisible: true
    headingPx: 48
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1440
    containerWidth: 1360
    gridColumns: 5
    navLinksVisible: 6
    menuToggleVisible: true
    headingPx: 48
    bodyPx: 16
    sectionPaddingX: 0
coverage:
  statesFound: 62
  gradientsFound: 3
  rolesUnassigned: 7
  archetypesUnnamed: 0
  archetypesDetected: 0
  responsiveMeasured: true
  stylesheetsBlocked: false
  semanticRampDeclared: false
---

# Design System Inspired by Gumloop

## 1. Visual Theme & Atmosphere

Gumloop's design system embodies a modern, technology-forward aesthetic built for serious enterprise AI work. The visual language combines crisp, minimalist surfaces with vibrant accent colors that signal interactivity and brand presence. Clean typography, ample whitespace, and a deliberately restrained color palette create an air of professionalism and precision. The system avoids unnecessary ornamentation—every element serves a function. Accent colors (particularly the brand blue) punctuate the interface with energy, while neutral grays and blacks maintain clarity and hierarchy. The overall effect is sophisticated, approachable, and designed to inspire confidence in complex AI agent workflows.

**Key Characteristics**
- Clean, minimal aesthetic with strong functional clarity
- High contrast between primary accent (`{colors.primary}` — `#1E8CFF`) and neutral backgrounds
- Generous whitespace and breathing room in layouts
- Sharp or subtly rounded corners depending on component role
- Typography-driven hierarchy with deliberate negative letter-spacing on display scales
- Depth achieved through color blocking and carefully layered shadows, not excessive elevation
- Accent palette includes decorative purples, greens, and blues for visual richness in secondary contexts

## 2. Color Palette & Roles

### Primary
- **Brand / Primary CTA** (`{colors.primary}` — `#1E8CFF`): Primary call-to-action buttons, brand accent elements, active states, and hero highlights. High-energy blue that commands attention and signals interactivity.

### Accent Colors
- **Secondary Accent** (`{colors.accent}` — `#522A10`): Secondary visual accent, often used in hero bands or decorative sections. Warm brown tone that adds sophistication and contrast to the primary blue.

### Decorative Accents
- **Decorative Purple Dark** (`{colors.accent-2}` — `#190D30`): Deep purple used as decorative element or background tint in specific sections.
- **Decorative Blue** (`{colors.accent-3}` — `#147BD1`): Mid-tone blue for decorative use; distinct from primary brand blue.
- **Decorative Purple** (`{colors.accent-4}` — `#8922EE`): Vibrant purple accent for agent icons and visual variety.
- **Decorative Purple Muted** (`{colors.accent-5}` — `#5B5FC7`): Muted purple used in decorative gradients and secondary visual elements.
- **Decorative Green** (`{colors.accent-6}` — `#95BF47`): Lime green for agent badges and icon accents.
- **Decorative Dark** (`{colors.accent-1}` — `#1C1A19`): Very dark brown or charcoal for decorative overlays and depth.

### Neutral Scale
- **Canvas / White** (`{colors.canvas}` — `#FFFFFF`): Default page background, card surfaces, and text color on brand-colored surfaces (labels, CTAs). Ensures maximum readability and clean layout.
- **Text / Black** (`{colors.neutral-1}` — `#000000`): Primary text color on light backgrounds. Used for headings, body copy, and high-contrast UI elements.

### Surface & Borders
The system derives surface colors from the white canvas with opacity variations:
- Subtle backgrounds use `oklab(1, 0, 0 / 0.05)` for minimal contrast borders and card backgrounds.
- Border colors employ light grays derived from lab-space calculations, typically `lab(93.26 0.81 -2.94)` or `lab(100 0 0 / 0.14)` for 1px dividing lines.

## 3. Typography Rules

### Font Family
- **Primary (Display & Headings):** Gellix, fallback to system sans-serif
- **Secondary (Body & UI):** GeistSans, fallback to system sans-serif
- **Tertiary (Code/Monospace):** GeistMono, fallback to monospace

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|---|---|---|---|---|---|---|
| Display | Gellix | 48px | 500 | 1.0 | -1.2px | Hero headline; aggressive negative tracking |
| Heading (Large) | Gellix | 36px | 500 | 1.25 | -0.9px | Subsection headings; strong visual weight |
| Heading (Medium) | Gellix | 20px | 500 | 1.25 | 0px | Section titles; balanced size |
| Quote | Gellix | 20px | 400 | 1.4 | 0px | Testimonials or callout text |
| Body (XL) | Gellix | 24px | 500 | 1.33 | 0px | Feature descriptions or emphasis |
| Body (Large) | Gellix | 16px | 500 | 1.5 | 0px | Rich body content with emphasis |
| Body (Medium) | GeistSans | 14px | 400 | 1.43 | 0px | Standard body copy and descriptions |
| Body (Medium Loose) | GeistSans | 14px | 400 | 1.55 | 0px | Body with extra line height for readability |
| Body (Small) | GeistSans | 13px | 400 | 1.38 | 0px | Secondary text and helper copy |
| Button (Large) | GeistSans | 18px | 500 | 1.56 | 0px | Large action buttons |
| Button (Medium) | GeistSans | 16px | 400 | 1.5 | 0px | Standard button text |
| Button (Small) | GeistSans | 13px | 600 | 1.5 | 0px | Compact button text; heavier weight |
| Button (Extra Small) | GeistSans | 12px | 400 | 1.38 | 0px | Minimal button labels |
| Navigation | GeistSans | 14px | 500 | 1.43 | 0px | Header nav links; medium weight for clarity |
| Caption (Medium) | GeistSans | 12px | 400 | 1.33 | 0px | Labels and small annotations |
| Caption (Medium Strong) | GeistSans | 12px | 500 | 1.33 | 0px | Emphasized labels and metadata |
| Caption (Small) | GeistSans | 11px | 400 | 1.5 | 0px | Tertiary text; fine print |
| Caption (Small Strong) | GeistSans | 11px | 500 | 1.5 | 0px | Emphasized small text |
| Caption (Extra Small) | GeistSans | 10px | 400 | 1.5 | 0px | Minimal metadata and fine annotations |
| Caption (Extra Small Strong) | GeistSans | 10px | 500 | 1.5 | 0px | Emphasized minimal text |
| Code | GeistMono | 60px | 300 | 1.0 | 0px | Monospace display (rarely used at this scale) |

### Principles
- **Negative tracking** on display and large heading scales (`-1.2px` on display, `-0.9px` on large headings) creates tightness and visual impact appropriate to hero contexts.
- **Weight hierarchy** uses 500–600 for headings and buttons to establish clear visual weight; body copy sits at 400 for readability.
- **Line height** increases slightly on body text (1.43–1.55) to maximize readability; display sizes compress to 1.0 for density.
- **Font switching** between Gellix (display/headings) and GeistSans (body/UI) creates visual distinction while maintaining coherent brand voice.
- **Button typography** varies by size and context: small buttons use heavier weights (600) to compensate for diminished size; larger buttons use moderate weights (400–500).

## 4. Component Stylings

### Buttons

**Primary Button**
- Background: `{colors.primary}` (`#1E8CFF`)
- Text Color: `{colors.canvas}` (`#FFFFFF`)
- Padding: `8px 10px`
- Font: `{typography.button-md}` (16px, 400 weight, GeistSans)
- Border Radius: `{rounded.lg}` (10px)
- Border: None
- Height: ~60px
- Box Shadow: None
- Hover: Text color follows interactive state (see Interaction States)

**Secondary Button (Text Style)**
- Background: `oklab(0.965 0.001 -0.004 / 0.45)` (translucent light)
- Text Color: `lab(8.71 -0.10 -1.58)` (very dark gray/black)
- Padding: `8px`
- Font: `{typography.nav}` (14px, 500 weight, GeistSans)
- Border Radius: `{rounded.md}` (8px)
- Border: None
- Height: ~28px
- Box Shadow: None

**Secondary Button (Text-Large)**
- Background: `lab(100 0 0)` (white)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Padding: `8px 18px`
- Font: `{typography.nav}` (14px, 500 weight)
- Border Radius: `{rounded.md}` (8px)
- Border: 1px solid `lab(90.01 0.81 -2.94)` (subtle border)
- Height: ~36px
- Box Shadow: `rgba(0,0,0,0) 0px 0px 0px 0px, rgba(0,0,0,0) 0px 0px 0px 0px, rgba(0,0,0,0) 0px 0px 0px 0px, rgba(0,0,0,0) 0px 0px 0px 0px, lab(90.01 0.81 -2.94) 0px 0px 0px 1px, rgba(0,0,0,0.016) 0px 1px 1px -0.5px, rgba(0,0,0,0.016) 0px 3px 3px -1.5px, rgba(0,0,0,0.01) 0px 6px 6px -3px, rgba(0,0,0,0.01) 0px 12px 12px -6px, rgba(0,0,0,0.01) 0px 24px 24px -12px`

**Filled Button (Light Primary)**
- Background: `rgb(194, 231, 255)` (light blue tint)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Padding: `12px 20px`
- Font: `{typography.nav}` (14px, 500 weight)
- Border Radius: `{rounded.lg}` (10px)
- Border: None
- Height: ~44px
- Box Shadow: None

### Cards & Containers

**Default Card**
- Background: `lab(100 0 0 / 0.05)` (near-white with 5% opacity tint)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: 1px solid `lab(100 0 0 / 0.14)` (subtle border)
- Padding: `0px` (content padding handled internally)
- Border Radius: `{rounded.md}` (8px)
- Box Shadow: None
- Font: `{typography.body-md}` (14px, 400 weight)

**Large Card (Full-Width)**
- Background: `lab(100 0 0)` (pure white)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: None
- Padding: `0px`
- Border Radius: `{rounded.none}` (0px / sharp corners)
- Box Shadow: None
- Font: `{typography.body-md}` (14px, 400 weight)

### Inputs & Forms

**Input Focus State**
- Border Color: Tailwind blue (`--blue-600`)
- Outline: `rgba(0, 0, 0, 0) solid 2px`
- Box Shadow: Composite ring shadow (`var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow)`)

**Input Hover State**
- Box Shadow: `var(--xy-node-boxshadow-hover)` or fallback

**Input Focus-Visible State**
- Box Shadow: `var(--xy-node-boxshadow-selected)` or fallback

### Navigation

**Header Navigation**
- Background: `rgba(0, 0, 0, 0)` (transparent)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Height: 53px
- Padding: `0px`
- Font: `{typography.nav}` (14px, 500 weight, GeistSans)
- Border: None
- Border Radius: `{rounded.none}` (0px)
- Box Shadow: None

**Navigation Link Hover**
- Background Color: `var(--sidebar-accent-foreground)` with opacity 3% blend, or `color-mix(in oklab, var(--sidebar-accent-foreground) 3%, transparent)`
- Text Color: `var(--muted-foreground)` or `color-mix(in oklab, var(--muted-foreground) 72%, transparent)`

### Badges

**Badge (Text)**
- Background: `lab(100 0 0)` (white)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: None
- Padding: `0px`
- Border Radius: `{rounded.full}` (9999px / pill shape)
- Font: `{typography.body-md}` (14px, 400 weight)
- Height: ~44px

**Badge (Text Variant 2)**
- Background: `rgba(0, 0, 0, 0)` (transparent)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: None
- Padding: `10px 16px`
- Border Radius: `{rounded.none}` (0px / sharp)
- Font: `{typography.body-md}` (14px, 400 weight)
- Height: ~44px

### Footer

**Footer Section**
- Background: `rgb(255, 255, 255)` (white)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Padding: `40px 0px` (vertical padding)
- Height: ~643px (full footer height)
- Font: `{typography.body-md}` (14px, 400 weight)
- Border: None
- Border Radius: `{rounded.none}` (0px)

### Links

**Default Link**
- Background: `lab(95.91 0.40 -1.45)` (very light gray)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: 1px solid `lab(93.26 0.81 -2.94)`
- Padding: `0px 24px`
- Border Radius: `{rounded.sm}` (6px)
- Font: `{typography.body-md}` (14px, 400 weight)

**Link (Inline)**
- Background: `rgba(0, 0, 0, 0)` (transparent)
- Text Color: `lab(8.71 -0.10 -1.58)`
- Border: None
- Padding: `6px 8px`
- Border Radius: `{rounded.none}` (0px)
- Font: `{typography.nav}` (14px, 500 weight)

## 5. Layout Principles

### Spacing System
The spacing system uses an 8px base unit with a logarithmic scale:
- `{spacing.xxs}` (4px): Micro adjustments and tight component spacing
- `{spacing.xs}` (8px): Minimal gaps between compact elements
- `{spacing.sm}` (12px): Small spacers within component groups
- `{spacing.md}` (16px): Standard padding inside cards and default component gutters
- `{spacing.lg}` (20px): Medium breathing room between related sections
- `{spacing.xl}` (24px): Comfortable spacing between distinct regions
- `{spacing.xxl}` (28px): Generous spacing for visual pause
- `{spacing.xxxl}` (32px): Substantial separation between major regions
- `{spacing.section}` (40px): Section-level padding; used for breaking visual flow
- `{spacing.band}` (48px): Hero bands and full-bleed sections with significant breathing room

### Grid & Container
- **Max Container Width:** 1200px (measured at 1280px viewport)
- **Content Column:** Adjusts with viewport: 343px (375px), 736px (768px), 992px (1024px), 1200px (1280px+)
- **Grid Columns:** Responsive 4–5 column grid; mobile uses 1–4 columns depending on section
- **Section Padding-X:** 0px (content handles its own margin within viewport constraints)
- **Column Strategy:** Asymmetric, content-driven layout with flexible grid support for varying page sections (hero, testimonials, features, clients)

### Whitespace Philosophy
Whitespace is treated as active design material. Large margins between sections create clear visual hierarchy and allow content to breathe. Hero sections use generous vertical spacing between headline and imagery. Card-based layouts rely on negative space around cards to establish grouping. Footer sections employ wide padding to avoid cramped presentations. The system avoids dense packing; when information density requires tighter spacing, it is confined to component internals, not section-level spacing.

### Border Radius Scale
- `{rounded.none}` (0px): Sharp cards, large containers, and full-width layouts; used on images and major structural elements
- `{rounded.xs}` (2px): Minimal rounding for subtle softness (rare; used on decorative elements)
- `{rounded.sm}` (6px): Link containers and cards with gentle curves
- `{rounded.md}` (8px): Buttons (secondary/text style), default cards, and medium containers; the most common UI rounding
- `{rounded.lg}` (10px): Primary buttons and prominent filled buttons; slightly more prominent than medium
- `{rounded.xl}` (12px): Decorative or secondary component accents
- `{rounded.full}` (9999px): Badge pills and fully circular elements

### Border Widths
- **Thin** (1px): Used on card borders (`lab(100 0 0 / 0.14)`) and link containers to define subtle boundaries without heavy visual weight

## 6. Depth & Elevation

| Level | Treatment | Use |
|---|---|---|
| Base (Flat) | No shadow; flat background `lab(100 0 0)` or `lab(100 0 0 / 0.05)` | Cards, default surfaces, standard layout |
| Subtle (Micro-Shadow) | Layered transparent shadows: `lab(90.01 0.81 -2.94) 0px 0px 0px 1px, rgba(0,0,0,0.016) 0px 1px 1px -0.5px, rgba(0,0,0,0.016) 0px 3px 3px -1.5px, rgba(0,0,0,0.01) 0px 6px 6px -3px, rgba(0,0,0,0.01) 0px 12px 12px -6px, rgba(0,0,0,0.01) 0px 24px 24px -12px` | Bordered secondary buttons and interactive elements; gives barely-there lift |

The elevation strategy is **color-blocking with micro-layering**. Depth comes primarily from surface color shifts—light backgrounds on white, muted backgrounds for secondary surfaces, and the brand blue for emphasis. Shadows are reserved for interactive feedback (buttons, hovered cards) and use a single micro-layered shadow formula that appears translucent and refined rather than pronounced. This keeps the interface flat and modern while providing visual feedback without visual clutter.

### Opacity Levels
- **35% (0.35):** Heavy transparency for muted or disabled states
- **50% (0.50):** Moderate transparency; used for overlay tints and background blends
- **64% (0.64):** Light transparency maintaining visibility
- **65% (0.65):** Near-opaque with subtle transparency
- **70% (0.70):** Mostly opaque with slight transparency for background washes
- **92% (0.92):** Nearly full opacity; subtle reduction for slightly recessed elements

### Z-index / Layering
- **Base** (z-index 1–2): Standard layout elements (cards, sections)
- **Dropdown** (z-index 10, 20, 30, 50): Overlays, modals, and popups; stacked in order of nesting depth
- **Sticky** (z-index 100): Fixed navigation, sticky headers, persistent elements

## 7. Do's and Don'ts

### Do
- **Use the primary blue** (`{colors.primary}` — `#1E8CFF`) for all primary call-to-action buttons and high-emphasis interactive elements. It is the most recognizable brand color and signals immediate affordance.
- **Maintain clean whitespace** around major content sections. Use `{spacing.section}` (40px) and `{spacing.band}` (48px) between distinct regions.
- **Apply negative letter-spacing** on display and large heading scales (`-1.2px` on 48px headlines, `-0.9px` on 36px headings). This tightness is a defining visual trait.
- **Use GeistSans for body and UI copy**, and reserve Gellix for display and heading scales only. This maintains visual clarity and hierarchy.
- **Layer shadows carefully**: only use the micro-shadow formula on interactive elements (buttons, hovered states). Keep most cards and surfaces flat.
- **Stick to the rounded scale** for consistency. Button radii are `{rounded.lg}` (10px) or `{rounded.md}` (8px); cards are `{rounded.md}` (8px) or `{rounded.none}` (0px) depending on context.
- **Test color contrast** between text and backgrounds. The system uses `lab(8.71 -0.10 -1.58)` (very dark) text on light backgrounds for accessibility.

### Don't
- **Invent new button styles.** Only primary, secondary (text), secondary-large, and filled variants exist. Combining them creates confusion.
- **Use decorative accent colors** (`{colors.accent-4}` through `{colors.accent-6}`) for interactive CTAs or system states. Reserve them for icons, badges, and secondary visual elements.
- **Apply heavy shadows** to everything. Shadows should be minimal and reserved for interactive feedback. Most surfaces should remain flat.
- **Compress whitespace** arbitrarily. Even on mobile, maintain breathing room with `{spacing.md}` (16px) to `{spacing.lg}` (20px) between sections.
- **Deviate from the typography hierarchy.** Using sizes outside the defined table (e.g. 15px body instead of 14px or 16px) breaks system cohesion.
- **Mix border-radius values.** Use only the defined scale: 0px, 2px, 6px, 8px, 10px, 12px, or 9999px. Arbitrary radii look unpolished.
- **Forget focus states.** Inputs and interactive elements must show clear focus outlines or border changes for keyboard navigation and accessibility.

## 8. Responsive Behavior

### Breakpoints

| Viewport | Content Column | Grid Columns | Nav Links Visible | Menu Toggle | Largest Heading | Body Text | Section Padding-X |
|---|---|---|---|---|---|---|---|
| 375px (Mobile) | 343px | 4 | 1 hidden | Yes | 36px | 16px | 0px |
| 768px (Tablet) | 736px | 4 | 1 hidden | Yes | 48px | 16px | 0px |
| 1024px (Desktop) | 992px | 5 | 6 visible | Yes | 48px | 16px | 0px |
| 1280px (Wide) | 1200px | 5 | 6 visible | Yes | 48px | 16px | 0px |
| 1440px (Extra Wide) | 1360px | 5 | 6 visible | Yes | 48px | 16px | 0px |

**Breakpoint Strategy:**
- Mobile navigation collapses to a menu toggle at 375px; nav links remain hidden until 1024px.
- Display headings (`{typography.display}` — 48px) scale down to `{typography.heading-md}` (36px) at 768px or smaller.
- Content columns expand incrementally: 343px → 736px → 992px → 1200px as viewport grows.
- Grid column count increases from 4 to 5 columns at 1024px+.
- Section padding-x remains 0px (handled by margin/padding on contained elements).

### Touch Targets
- **Minimum button height:** 44px (ensures comfortable tapping on mobile)
- **Minimum link/interactive area:** 36px × 36px (follows WCAG guidelines)
- **Navigation link spacing:** `{spacing.md}` (16px) horizontal gap between links for touch ergonomics

### Collapsing Strategy
- **Hero section:** Full-width image/video at all sizes; headline scales (36px on mobile, 48px on desktop).
- **Navigation:** Transforms to hamburger menu at <1024px breakpoint; drawer/overlay menu appears on mobile.
- **Grid layouts:** 4-column grid on tablet/mobile shifts items to stack vertically if content requires; maintains 5-column at desktop.
- **Card rows:** Cards remain full-width at 375px; begin horizontal stacking at 768px, reaching 2–3 columns at 1024px+.
- **Typography:** Body text stays 16px across all breakpoints for readability; reduces to 14px only in captions/metadata on mobile.
- **Padding:** Section padding-x is managed by container margins, not explicit breakpoint changes; section vertical padding (`{spacing.section}` / `{spacing.band}`) stays constant.

## 9. Agent Prompt Guide

### Quick Color Reference
- **Primary CTA:** Brand Blue (`{colors.primary}` — `#1E8CFF`)
- **Canvas/Background:** White (`{colors.canvas}` — `#FFFFFF`)
- **Text/Heading:** Black (`{colors.neutral-1}` — `#000000`)
- **Button Secondary:** Light translucent (`oklab(0.965 0.001 -0.004 / 0.45)`)
- **Card Background:** Near-white with border (`lab(100 0 0 / 0.05)`, border: `lab(100 0 0 / 0.14)`)
- **Secondary Accent:** Brown (`{colors.accent}` — `#522A10`)
- **Decorative Accents:** Purple (`#8922EE`, `#5B5FC7`), Blue (`#147BD1`), Green (`#95BF47`)

### Iteration Guide
1. **Always use `{colors.primary}` (`#1E8CFF`) for primary action buttons.** Secondary and tertiary buttons use light, translucent, or white backgrounds.
2. **Apply negative letter-spacing strictly to display (−1.2px) and large headings (−0.9px).** Body and UI text use 0px letter-spacing.
3. **Button border-radius is `{rounded.lg}` (10px) for primary/filled; `{rounded.md}` (8px) for secondary.** Cards default to `{rounded.md}` (8px) or `{rounded.none}` (0px).
4. **Cards use flat backgrounds** (`lab(100 0 0 / 0.05)` with 1px border) **or pure white (`lab(100 0 0)`).** Shadows are rare; use only the micro-layered shadow on interactive elements.
5. **Spacing between sections is generous:** use `{spacing.section}` (40px) or `{spacing.band}` (48px) as the baseline. Compress only within component internals.
6. **Typography hierarchy is fixed.** Display is 48px (Gellix), headings are 36px or 20px (Gellix), body is 14–16px (GeistSans), captions are 10–12px (GeistSans). Do not invent intermediate sizes.
7. **Navigation collapses at <1024px to a menu toggle.** Header remains transparent (`rgba(0,0,0,0)`), nav links use 14px weight-500 GeistSans.
8. **Focus states on inputs show border-color: `--blue-600` and composite ring shadow.** Keyboard users must see clear focus indicators.
9. **Opacity levels for disabled/muted states range 35–92%.** Use 50% or 65% for standard transparency overlays; 35% for heavily muted elements.
10. **Z-index layering:** base (1–2), dropdowns (10–50), sticky nav (100). Do not exceed 100 unless modals or critical overlays require it.

## 10. Known Gaps

- **Semantic Status Colors:** No error, success, warning, or info colors are declared in the site markup. The extraction found no semantic color ramp. If your implementation requires status feedback, you must source these externally or define them as an extension to this system.
- **Unassigned Decorative Colors:** Seven colors (`{colors.accent-1}` through `{colors.accent-6}`, excluding primary and accent-1 which are used for agent icons) have no measured functional role and appear only in decorative contexts (agent badge icons, gradient backgrounds). Their usage beyond what was observed is not defined.
- **Dark Mode / Theme Variants:** This extraction captured only the light theme visible on the page. No dark mode or alternate theme data was collected. If dark mode exists behind authentication or on another surface, it is not documented here.
- **Interaction States Beyond Hover/Focus:** The site's stylesheets declare `:hover`, `:focus`, and `:focus-visible` states but do not expose active, disabled, or loading states in the captured CSS. Implement these as needed for completeness, but do not reference them as part of this system's documented design.
- **Component Variants Not Observed:** Only the buttons, cards, inputs, badges, navigation, footer, and links listed above were present on the captured page. Other components (modals, dropdowns, tabs, accordions, tooltips, etc.) were not measured. Extend this system with consistency, but recognize such components are extensions, not documented specifications.
- **Animation & Transition Timing:** No CSS animations, transitions, or keyframes were extracted. Hover and focus state changes are implied but not timed. Define transition durations (e.g. 200ms for color changes) according to your interaction design.
- **Shadow Variations:** Only one shadow formula (the micro-layered variant) was observed in the component data. More complex shadows or elevation states may exist in unvisited surfaces (authenticated areas, modals, etc.).
- **Font Licensing & Availability:** Gellix, GeistSans, and GeistMono are referenced by name but assume these fonts are properly licensed and served by your environment. Fallback stacks are generic system fonts; ensure fallback weights match intended hierarchy.
- **Accessibility Details:** ARIA attributes, semantic HTML roles, and alt text strategies are not captured. Implement accessibility features independently, ensuring color contrast meets WCAG AA+ (the text/background pairs do—lab(8.71) on lab(100) is extremely high contrast).