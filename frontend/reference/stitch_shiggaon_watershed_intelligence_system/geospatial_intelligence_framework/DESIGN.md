---
name: Geospatial Intelligence Framework
colors:
  surface: '#f7fbf1'
  surface-dim: '#d4ddce'
  surface-bright: '#f4fced'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eef6e7'
  surface-container: '#ecefe6'
  surface-container-high: '#e2ebdc'
  surface-container-highest: '#dde5d6'
  on-surface: '#161d14'
  on-surface-variant: '#41493e'
  inverse-surface: '#2b3328'
  inverse-on-surface: '#ebf3e4'
  outline: '#717a6d'
  outline-variant: '#c0c9bb'
  surface-tint: '#2a6b2c'
  primary: '#00450d'
  on-primary: '#ffffff'
  primary-container: '#1b5e20'
  on-primary-container: '#90d689'
  inverse-primary: '#91d78a'
  secondary: '#01629e'
  on-secondary: '#ffffff'
  secondary-container: '#7cbeff'
  on-secondary-container: '#004c7d'
  tertiary: '#6b1d3d'
  on-tertiary: '#ffffff'
  tertiary-container: '#883454'
  on-tertiary-container: '#ffaec6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#acf4a4'
  primary-fixed-dim: '#91d78a'
  on-primary-fixed: '#002203'
  on-primary-fixed-variant: '#0c5216'
  secondary-fixed: '#cfe5ff'
  secondary-fixed-dim: '#9acbff'
  on-secondary-fixed: '#001d34'
  on-secondary-fixed-variant: '#004a79'
  tertiary-fixed: '#ffd9e2'
  tertiary-fixed-dim: '#ffb1c8'
  on-tertiary-fixed: '#3e001d'
  on-tertiary-fixed-variant: '#7a2949'
  background: '#f4fced'
  on-background: '#161d14'
  surface-variant: '#dde5d6'
  border-subtle: '#c0c9bb'
  border-strong: '#717a6d'
  status-valid: '#2e7d32'
  status-missing: '#757575'
  status-suspicious: '#d32f2f'
  status-review: '#ed6c02'
  status-inside: '#0288d1'
  status-outside: '#7b1fa2'
typography:
  display:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  headline-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: jetbrainsMono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 12px
  margin-sm: 8px
  margin-md: 16px
  panel-gap: 4px
  sidebar-w: 60px
  sidebar-expanded: 240px
---

## Brand & Style

The design system is a high-precision interface engineered for geospatial analysis, environmental monitoring, and mission-critical decision-making. It adopts a **Corporate / Modern** style infused with **Minimalist** rigor, prioritizing information density and technical clarity over decorative elements.

The aesthetic is "research-grade"—it feels like a professional scientific instrument. The visual narrative is built on:
- **Maximum Utility:** Every pixel serves a functional purpose, utilizing a compact layout to maximize data visibility.
- **Authority & Trust:** A primary palette of deep greens conveys stability and institutional reliability.
- **Clarity under Pressure:** High-contrast ratios and a lack of depth effects (like shadows or blurs) ensure that the interface remains legible in diverse lighting conditions and complex GIS environments.
- **Zero Distraction:** Decorative graphics, rounded containers, and animations are eschewed in favor of a clean, structured, and "unrefined" professional efficiency.

## Colors

The color strategy is designed for categorical precision and institutional authority. 

- **Primary Green (#1B5E20):** Used for primary actions, navigation indicators, and brand presence. It signifies growth and environmental focus.
- **Secondary Blue:** Reserved for GIS-specific interactions, water features, and interactive map layers.
- **Functional Grays:** The neutral palette uses a slightly warm "Olive-Gray" to reduce eye strain during long analytical sessions while maintaining high contrast.
- **GIS/ML Status Palette:** 
    - **VALID:** Forest Green (System success)
    - **MISSING:** Medium Gray (Data void)
    - **SUSPICIOUS:** High-alert Red (Anomaly detected)
    - **BOUNDARY_REVIEW:** Deep Orange (Human intervention required)
    - **INSIDE/OUTSIDE:** Technical Blue/Purple (Spatial relationship indicators)

## Typography

Typography is the backbone of the framework's density. The system uses **Inter** for its neutral tone and excellent legibility at small sizes. 

- **Numerical Precision:** All coordinate data, timestamps, and sensor metrics must use **JetBrains Mono** or Inter with `tabular-nums` enabled to ensure vertical alignment in tables.
- **Density Control:** Body text is set slightly smaller than standard consumer apps (13px/15px) to allow for more content per screen.
- **Labels:** `label-sm` is used for metadata and table headers. It is always uppercase with increased letter spacing to distinguish it from interactive text.
- **Mobile Adjustments:** Headlines scale down by 15% on mobile devices to prevent awkward wrapping in data sidebars.

## Layout & Spacing

The layout follows a **Rigid Grid** philosophy based on a 4px increment system.

- **The GIS Viewport:** The primary map occupies the central fluid space. All data panels are docked as persistent sidebars or floating overlays.
- **Panel Construction:** Use `panel-gap` (4px) between adjacent data modules to create a "tiled" look. This maximizes real estate while maintaining clear separation.
- **Fixed/Fluid Hybrid:** Sidebars are fixed-width to ensure chart and table consistency, while the map scales to fill the remaining viewport.
- **Breakpoints:**
    - **Desktop (1280px+):** Full 3-column layout (Left: Navigation/Layers, Center: Map, Right: Details/Attributes).
    - **Tablet (768px-1279px):** Sidebars collapse to "Rail" mode (60px width) and expand on hover/click.
    - **Mobile (<768px):** Map occupies top 40% of the screen; data panels stack vertically below.

## Elevation & Depth

To maintain a flat, professional, and high-density appearance, this design system rejects traditional shadows. Depth is communicated through **Tonal Layering** and **Low-Contrast Outlines**.

- **Level 0 (Base):** The `surface` color (#F7FBF1) used for the main application background.
- **Level 1 (Panels):** `surface-container` (#ECEFE6) with a 1px `border-subtle` (#C0C9BB). No shadow.
- **Level 2 (Active/Floating):** Use a slightly brighter surface or a 1px `border-strong` (#717A6D) for elements that sit above the map, such as toolbars or context menus.
- **Focus States:** Elements receive a 2px solid primary color outline; do not use soft glows or blurs.

## Shapes

The shape language is **Soft (0.25rem)**, bordering on sharp. This minimal rounding provides a slight modern affordance without sacrificing the "engineered" feel of a technical framework.

- **Inputs & Buttons:** 4px (0.25rem) radius.
- **Cards & Panels:** 4px (0.25rem) radius.
- **Status Badges:** Strictly rectangular or 2px radius to avoid being confused with interactive "Pill" buttons.
- **Selection Indicators:** Hard, 0px-radius vertical bars (3px wide) are used to indicate active navigation items.

## Components

### Precise Status Badges
Status indicators must use the `named_colors` palette. They are rendered with a 10% opacity background of the status color and a 100% opacity 1px border. Text is `label-sm` in the status color.

### Compact Data Tables
- **Row Height:** Strictly 32px (standard) or 28px (dense).
- **Headers:** `surface-container` background, `label-sm` text, bottom-aligned 1px border.
- **Cell Content:** Use `mono-data` for all coordinates and IDs. No cell padding on the left/right edges of the table to maximize horizontal space.

### Input Fields
- **Treatment:** Strictly 1px border (#717A6D) with no background fill.
- **Focus:** Border changes to `primary` with a 1px inset outline.
- **Labels:** Always displayed above the input using `label-md`. Never use floating labels or placeholder-only styles.

### Card Treatments
- **Header:** 1px bottom border separating the title area from the content.
- **Content:** Minimal padding (8px or 12px).
- **Shadows:** Prohibited. Use 1px borders for all card definitions.

### GIS Toolbars
Group icons into solid blocks with 1px internal dividers. The active tool should have a `primary` background with a white icon. Background should be `surface-container-lowest` (#FFFFFF).