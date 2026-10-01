#!/usr/bin/env bash
# Rebuild assets/fonts/toolbar-icons.woff2 from upstream.
#
# Source: Material Symbols Outlined variable font, Apache License 2.0,
# https://github.com/google/material-design-icons (variablefont/).
# The font is subset here to the 7 toolbar glyphs and pinned to a single
# instance (FILL=0, GRAD=0, opsz=24, wght=400), then the app embeds the
# result as a base64 data URI — no CDN, the app never needs the network
# for its own chrome.
#
# PUA codepoints (from MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].codepoints):
#   tag          E9EF   Update Hashtags
#   image        E3F4   Update Images
#   newspaper    EB81   Update News
#   refresh      E5D5   Reset
#   share        E80D   Share
#   content_copy E14D   Copy
#   delete       E92E   Delete
set -euo pipefail
cd "$(dirname "$0")"
BASE="https://raw.githubusercontent.com/google/material-design-icons/master/variablefont"
FILE="MaterialSymbolsOutlined%5BFILL%2CGRAD%2Copsz%2Cwght%5D"
curl -sSL --max-time 120 "$BASE/$FILE.woff2" -o ms_full.woff2
python3 - <<'EOF'
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
f = TTFont("ms_full.woff2")
instantiateVariableFont(f, {"FILL": 0, "GRAD": 0, "opsz": 24, "wght": 400}, inplace=True)
f.save("ms_inst.ttf")
EOF
python3 -m fontTools.subset ms_inst.ttf \
  --unicodes="U+E9EF,U+E3F4,U+EB81,U+E5D5,U+E80D,U+E14D,U+E92E" \
  --flavor=woff2 --layout-features='' --no-hinting --desubroutinize \
  --output-file=toolbar-icons.woff2
rm -f ms_full.woff2 ms_inst.ttf
ls -la toolbar-icons.woff2
