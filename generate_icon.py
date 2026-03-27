"""One-time script: generates assets/icon.ico with a stylized 'G'."""

import os
from PIL import Image, ImageDraw, ImageFont


def _render(size: int) -> Image.Image:
    """Render icon at given size using 4x supersampling."""
    ss = size * 4  # supersample factor
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(2, ss // 32)
    radius = ss // 5
    draw.rounded_rectangle(
        [pad, pad, ss - pad - 1, ss - pad - 1],
        radius=radius, fill="#141614",
    )

    font_size = int(ss * 0.6)
    try:
        font = ImageFont.truetype("segoeuib.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "G", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (ss - tw) / 2 - bbox[0]
    y = (ss - th) / 2 - bbox[1]
    draw.text((x, y), "G", fill="#e8e8e8", font=font)

    # Downscale with LANCZOS
    return img.resize((size, size), Image.LANCZOS)


def generate():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [_render(s) for s in sizes]

    out = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Save — first image is base, rest appended
    images[0].save(
        out, format="ICO",
        append_images=images[1:],
    )

    # Also save 256px PNG for external use
    png_out = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    images[-1].save(png_out, format="PNG")

    print(f"Created {out} and {png_out}")


if __name__ == "__main__":
    generate()
