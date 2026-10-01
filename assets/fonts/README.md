# Toolbar icon font

`toolbar-icons.woff2` (1.2 KB) is a subset of **Material Symbols Outlined**
pinned to one instance (FILL=0, GRAD=0, opsz=24, wght=400).

- **Source:** https://github.com/google/material-design-icons
- **License:** Apache License 2.0 — free for commercial use, no attribution
  required for the font binary. (The Apache 2.0 text is not bundled here;
  see the source repository.)
- **Why this set:** one consistent outlined stroke language across all
  seven story-detail toolbar glyphs (Update Hashtags / Images / News,
  Reset, Share, Copy, Delete); PUA codepoints (not ligatures) so each
  Streamlit button label is a single character; self-hosted via a base64
  data URI in `library_ui.py` — no CDN, the app never needs the network
  for its own chrome.
- **Rebuild:** `./build_toolbar_icons.sh` (needs `fonttools`).

| Glyph | Codepoint | Toolbar action |
|---|---|---|
| tag | U+E9EF | Update Hashtags |
| image | U+E3F4 | Update Images |
| newspaper | U+EB81 | Update News |
| refresh | U+E5D5 | Reset |
| share | U+E80D | Share |
| content_copy | U+E14D | Copy |
| delete | U+E92E | Delete |
