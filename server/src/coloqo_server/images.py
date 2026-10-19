"""Recognising the raster images the web shows inline (decision 0018)."""

SIGNATURE_BYTES = 12
"""How many first bytes of a file decide whether it is an image."""


def image_type(head: bytes) -> str | None:
    """Return the media type of a raster image the web may show, judged by its first bytes.

    Only PNG, JPEG, GIF and WebP are recognised; SVG and everything else are not, since they
    can carry scripts. The type the uploader declared is not consulted.

    Args:
        head: The first ``SIGNATURE_BYTES`` bytes of the content, or all of it if shorter.
    """
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None
