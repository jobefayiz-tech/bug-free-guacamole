import io

from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 60_000_000
MAX_SIDE = 1600


def process_upload(file_storage):
    """Validate an uploaded photo and return clean JPEG bytes (EXIF/GPS stripped, resized).

    Raises ValueError with an Arabic message if the file is not a usable image.
    """
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("الملف ليس صورة صالحة (استخدم JPG أو PNG)")
    if img.format not in ("JPEG", "PNG", "WEBP"):
        raise ValueError("صيغة الصورة غير مدعومة (استخدم JPG أو PNG)")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)  # no exif passed => stripped
    return out.getvalue()
