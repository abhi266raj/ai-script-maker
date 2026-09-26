#!/usr/bin/env python3
"""Generate AppIcon-Dev.icns — production icon with a red 'DEV' banner overlay."""
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ICONSET = os.path.join(PROJECT, "AppIcon.iconset")
OUTPUT_ICNS = os.path.join(PROJECT, "AppIcon-Dev.icns")


def _overlay_dev_banner(img: Image.Image) -> Image.Image:
    """Draw a diagonal red 'DEV' banner on the bottom-right corner."""
    img = img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- diagonal banner geometry ---
    # Banner stripe runs from bottom-left area to top-right area
    band_width = int(w * 0.28)  # thickness of the banner ribbon

    # Four corners of the diagonal band (bottom-right quadrant)
    pts = [
        (w * 0.38, h),        # bottom-left start
        (w, h * 0.38),        # top-right start
        (w, h * 0.38 + band_width),  # top-right end
        (w * 0.38 + band_width, h),  # bottom-left end
    ]
    draw.polygon([(int(x), int(y)) for x, y in pts], fill=(210, 30, 30, 230))

    # --- "DEV" text ---
    font_size = max(int(band_width * 0.55), 8)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/SFNSMono.ttf", font_size
            )
        except Exception:
            font = ImageFont.load_default()

    # Centre of the banner
    cx = (pts[0][0] + pts[1][0]) / 2 + band_width / 4
    cy = (pts[0][1] + pts[1][1]) / 2 + band_width / 4

    # Render text on a temporary image, rotate, paste
    txt_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    bbox = txt_draw.textbbox((0, 0), "DEV", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = int(cx - tw / 2)
    ty = int(cy - th / 2)
    txt_draw.text((tx, ty), "DEV", fill=(255, 255, 255, 255), font=font)
    txt_img = txt_img.rotate(45, center=(int(cx), int(cy)), resample=Image.BICUBIC)

    overlay = Image.alpha_composite(overlay, txt_img)
    return Image.alpha_composite(img, overlay)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        dev_iconset = os.path.join(tmp, "AppIcon-Dev.iconset")
        shutil.copytree(SRC_ICONSET, dev_iconset)

        for fname in sorted(os.listdir(dev_iconset)):
            if not fname.endswith(".png"):
                continue
            path = os.path.join(dev_iconset, fname)
            img = Image.open(path)
            result = _overlay_dev_banner(img)
            result.save(path)
            print(f"  ✅ {fname} ({img.size[0]}×{img.size[1]})")

        # iconutil to compile .iconset → .icns
        subprocess.run(
            ["iconutil", "-c", "icns", dev_iconset, "-o", OUTPUT_ICNS],
            check=True,
        )
        print(f"\n📦 {OUTPUT_ICNS}")


if __name__ == "__main__":
    main()
