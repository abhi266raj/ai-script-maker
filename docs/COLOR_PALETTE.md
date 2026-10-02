# COLOR_PALETTE.md — Khabarwaani Admin Theme

**Single source of truth for the app's color system.** User-supplied spec,
verbatim. Every token below lives as a CSS variable in `app.py`'s theme
`<style>` block (the `KHABARWAANI ADMIN THEME — SINGLE SOURCE OF TRUTH`
comment). Component CSS must reference these tokens — never hard-coded hex.

---

## STYLE

Warm paper background, warm ink text, one orange accent. Neutral by default,
colour is rare.

## BALANCE

~60% paper, ~25% surfaces (card/popover), ~5% accent tint, at most 10%
orange, under 2% danger red.

## RULES

1. Orange (`--accent`) is for ONE primary action per screen, the toggle
   when on, the focus ring and the selected-item bar.
2. Selected or hovered items use `--accent-tint` or `--hover`, never a blue
   or grey-blue.
3. Red (`--danger`) means destructive only. Delete buttons are transparent
   with red icon/text and fill with `--danger-tint` on hover.
4. Popovers, menus and modals use `--popover`, a 1px `--line` border, and a
   soft shadow. Modal backdrop uses `--scrim`.
5. Secondary text is `--ink-2`. Placeholders and disabled use `--ink-3`.
   Never use pure black or pure white text.
6. Use green/amber (success/warning) only for status badges and toasts.
   No blue for info; use ink or grey.
7. All buttons: 36px height, 10px radius, 1px `--line` border. Support light
   and dark by switching the variables on `:root[data-theme="dark"]`.

---

## TOKEN TABLE

| Token | Light | Dark | Use | Avoid |
|---|---|---|---|---|
| `--paper` | `#F5F3EE` | `#1C1B19` | Page background only (~60% of screen) | Never text/buttons directly on it without a surface |
| `--card` | `#FFFFFF` | `#262522` | Cards, toolbars, default buttons | Never page background |
| `--sunken` | `#EFECE4` | `#2E2D29` | Inputs, code blocks, inactive chips | Never raised surfaces |
| `--popover` | `#FFFFFF` | `#2E2D29` | Dropdowns, menus, dialogs (+ border + shadow) | Never page background |
| `--hover` | `#F0EDE5` | `#34332E` | Row/menu/button hover | Never selected state (use accent-tint) |
| `--scrim` | `rgba(31, 30, 27, .40)` | `rgba(0, 0, 0, .60)` | Modal backdrop only | Never a visible UI surface |
| `--line` | `#E3DFD5` | `#3A3833` | 1px borders/dividers | Never text or large fills |
| `--line-strong` | `#CFCABD` | `#4A4740` | Input hover, emphasis borders | Never text or large fills |
| `--ink` | `#1F1E1B` | `#F1EEE6` | Titles, body, icons | Never large fills |
| `--ink-2` | `#6B675F` | `#A39E92` | Hints, counts, inactive icons | Never primary content |
| `--ink-3` | `#9A958A` | `#77726A` | Placeholders/disabled only | Never anything that must be read |
| `--on-accent` | `#FFFFFF` | `#1C1B19` | Label on primary button only | Never on any other colour |
| `--accent` | `#E0692A` | `#EA7A3D` | ONE main action per screen, toggle on, focus ring, active bar | Never delete buttons or large areas (≤10%) |
| `--accent-hover` | `#C9581D` | `#F28C54` | Primary-button hover only | Anywhere else |
| `--accent-tint` | `#F8E6DA` | `#3A2A20` | Selected story/row, soft badges | Never text colour |
| `--danger` | `#B3382C` | `#E5604F` | Delete icon/text, error messages; fill only on hover | Never decoration or toggles |
| `--danger-tint` | `#F7E4E1` | `#3A2220` | Delete hover, error banner | Never text |
| `--success` | `#3F7D58` | `#5DAE7F` | Status badges and toasts only | Anywhere else |
| `--success-tint` | `#E3F0E8` | `#1F2E25` | Status badges and toasts only | Text colour |
| `--warning` | `#A8741A` | `#D9A441` | Status badges and toasts only | Anywhere else |
| `--warning-tint` | `#F7ECD6` | `#33291A` | Status badges and toasts only | Text colour |
| `--radius` | `10px` | `10px` | Buttons, inputs, cards | — |
| `--radius-lg` | `12px` | `12px` | Popovers, menus, modals | — |
| `--shadow-sm` | `0 1px 2px rgba(31, 30, 27, .06)` | `none` | Buttons, small raised elements | Dark mode (none) |
| `--shadow-pop` | `0 8px 24px rgba(31, 30, 27, .12)` | `0 8px 24px rgba(0, 0, 0, .40)` | Popovers, menus, modals | Flat surfaces |

Derived (not user-supplied; documented here, defined in `app.py`):

| Token | Light | Dark | Use |
|---|---|---|---|
| `--quaternary` | `#C4BFAF` | `#57534A` | Decorative-only tier, strictly faintest; never essential text |

---

## CSS TO PASTE

```css
:root {
  /* Layers */
  --paper:        #F5F3EE;  /* page background */
  --card:         #FFFFFF;  /* panels, buttons */
  --sunken:       #EFECE4;  /* inputs, chips, code */
  --popover:      #FFFFFF;  /* dropdowns, menus, modals, tooltips */
  --hover:        #F0EDE5;  /* row / menu item hover */
  --scrim:        rgba(31, 30, 27, .40);  /* modal overlay */

  /* Lines */
  --line:         #E3DFD5;  /* default border */
  --line-strong:  #CFCABD;  /* input hover, emphasis */

  /* Text */
  --ink:          #1F1E1B;  /* primary text, icons */
  --ink-2:        #6B675F;  /* secondary text, hints */
  --ink-3:        #9A958A;  /* disabled, placeholders */
  --on-accent:    #FFFFFF;  /* text on orange */

  /* Brand */
  --accent:       #E0692A;  /* primary action, toggle on, focus */
  --accent-hover: #C9581D;
  --accent-tint:  #F8E6DA;  /* selected item, soft highlight */

  /* Status */
  --danger:       #B3382C;
  --danger-tint:  #F7E4E1;
  --success:      #3F7D58;
  --success-tint: #E3F0E8;
  --warning:      #A8741A;
  --warning-tint: #F7ECD6;

  /* Shape */
  --radius:       10px;
  --radius-lg:    12px;
  --shadow-sm:    0 1px 2px rgba(31, 30, 27, .06);
  --shadow-pop:   0 8px 24px rgba(31, 30, 27, .12);
}

/* Dark: manual override */
:root[data-theme="dark"] {
  --paper:        #1C1B19;
  --card:         #262522;
  --sunken:       #2E2D29;
  --popover:      #2E2D29;
  --hover:        #34332E;
  --scrim:        rgba(0, 0, 0, .60);

  --line:         #3A3833;
  --line-strong:  #4A4740;

  --ink:          #F1EEE6;
  --ink-2:        #A39E92;
  --ink-3:        #77726A;
  --on-accent:    #1C1B19;

  --accent:       #EA7A3D;
  --accent-hover: #F28C54;
  --accent-tint:  #3A2A20;

  --danger:       #E5604F;
  --danger-tint:  #3A2220;
  --success:      #5DAE7F;
  --success-tint: #1F2E25;
  --warning:      #D9A441;
  --warning-tint: #33291A;

  --shadow-sm:    none;
  --shadow-pop:   0 8px 24px rgba(0, 0, 0, .40);
}

/* Dark: follow system unless user chose light */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* same values as above */ }
}
```

---

## HOW TO CHANGE COLORS

1. **Edit only the `:root` token values** (in `app.py`'s theme block, or in
   the raw `--pal-*` palette those tokens reference). Do not invent new
   colours — use only the tokens in the table above.
2. **Component CSS must reference tokens** (`var(--accent)`, `var(--line)`,
   …), never hard-coded hex. The contrast test suite fails loudly on hex
   literals outside the `:root` palette blocks.
3. **Verify after any change:**
   - `pytest tests/test_theme_palette_contrast.py` — essential text pairs
     ≥ 4.5:1 (WCAG AA); the user's explicit sub-4.5 values (light primary
     button, light success/warning solids) are pinned at the ≥ 3:1
     large-text/UI floor with their exact measured ratios — the test
     fails if they drift lower.
   - Rule-by-rule check against the RULES section above: one orange
     primary action per screen, no blue anywhere, delete buttons quiet
     until hover, toggles never red, no pure black/white text.
4. The four semantic roles map onto this palette: `--primary` → `--accent`,
   `--secondary` → `--ink-2`, `--tertiary` → `--ink-3`,
   `--quaternary` → decorative warm gray (see derived table).
