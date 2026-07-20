import io
import os
import random
from PIL import Image, ImageOps

# ===== 参数 =====
INPUT_DIR = "wife"

LONG_EDGE = 800          # 长边
TARGET_KB = 250          # 目标大小
NOISE_LEVEL = 2          # 0=关闭
MIN_QUALITY = 60
MAX_QUALITY = 100
# =================


def add_noise(img, level):
    if level <= 0:
        return img

    pixels = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + random.randint(-level, level))),
                max(0, min(255, g + random.randint(-level, level))),
                max(0, min(255, b + random.randint(-level, level))),
            )
    return img


def resize_keep_ratio(img):
    w, h = img.size

    if max(w, h) <= LONG_EDGE:
        return img

    scale = LONG_EDGE / max(w, h)

    return img.resize(
        (int(w * scale), int(h * scale)),
        Image.Resampling.LANCZOS,
    )


def compress(img):
    low = MIN_QUALITY
    high = MAX_QUALITY
    best = None

    while low <= high:
        q = (low + high) // 2

        buf = io.BytesIO()
        img.save(
            buf,
            format="JPEG",
            quality=q,
            optimize=True,
            progressive=True,
        )

        size = buf.tell() / 1024

        if size <= TARGET_KB:
            best = buf.getvalue()
            low = q + 1
        else:
            high = q - 1

    if best is None:
        buf = io.BytesIO()
        img.save(
            buf,
            format="JPEG",
            quality=MIN_QUALITY,
            optimize=True,
            progressive=True,
        )
        best = buf.getvalue()

    return best


def process(path):
    img = Image.open(path)

    # 修正EXIF方向
    img = ImageOps.exif_transpose(img)

    # 去Alpha
    img = img.convert("RGB")

    img = resize_keep_ratio(img)

    img = add_noise(img, NOISE_LEVEL)

    data = compress(img)

    out = os.path.splitext(path)[0] + ".jpg"

    with open(out, "wb") as f:
        f.write(data)

    if out != path:
        os.remove(path)

    print(f"{os.path.basename(out):30s} {len(data)/1024:6.1f} KB")


def main():
    for name in os.listdir(INPUT_DIR):
        path = os.path.join(INPUT_DIR, name)

        if os.path.isfile(path):
            try:
                process(path)
            except Exception as e:
                print(name, e)


if __name__ == "__main__":
    main()
