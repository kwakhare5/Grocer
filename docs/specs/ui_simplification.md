# Spec: Swiggy Instamart Dashboard Simplification

This document details the visual style and content changes to align the Instamart Intelligence dashboard with a clean, easy-to-understand, non-technical layout matching Swiggy's branding.

## 1. Visual Theme (Swiggy Aesthetic)
- **Background**: Soft gray/warm white `var(--background)` (`#f7f6f3` or `#faf9f7`).
- **Cards**: Clean white `var(--surface)` with thin light borders.
- **Accents**: Swiggy Orange (`#ff5a00` / `var(--accent)`) for primary call-to-actions, hover effects, and active highlights.
- **Typography**: Complete removal of monospace/coder fonts (`font-mono` / `.font-data`) from primary text elements (headings, titles, descriptions). Monospace should only be used for small data indicators where secondary.

## 2. Copy/Terminology Translation (Anti-Jargon)
- **T-1d / T-2d**: `"Out tomorrow!"` (Critical) / `"2 days left"` (Low).
- **CONF: 87%**: Hidden behind qualitative certainty tags, or shown on tooltip as `"High accuracy prediction"`.
- **AVG 1.1 L/day**: `"Usually uses 1.1 L every day"`.
- **CYCLE 2.1d**: `"Restocked every 2 days"`.
- **Household Dossier**: `"My Kitchen Profile"`.
- **Depletion Predictions**: `"Pantry Timeline"`.
- **Recipe Intelligence**: `"Meal Planner"`.
- **Price Intelligence**: `"Price Alerts"`.

## 3. New Component Actions
- **Add to Cart**:
  - Adds the item to the user's active shopping cart.
  - Instantly toggles button text from `Add to Cart` to `✓ Added`.
- **Pin to Sunday**:
  - Pins the item to the Sunday meal checklist.
  - Triggers a browser toast notification: `"Pinned [Item] to your Sunday Meal Plan!"`.
- **Pause Alerts**:
  - Opens a clean inline popover / dropdown offering:
    - `"Snooze 3 Days"`
    - `"Snooze 1 Week"`
    - `"Stop tracking this item"`
  - Toggles the card view to a grayed out or dismissed state with a Toast feedback.
