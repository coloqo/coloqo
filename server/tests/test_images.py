"""Tests of recognising the raster images the web shows inline (decision 0018)."""

import pytest

from coloqo_server.images import image_type


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\r", "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", "image/jpeg"),
        (b"GIF89a\x01\x00\x01\x00\x80\x00", "image/gif"),
        (b"GIF87a\x01\x00\x01\x00\x80\x00", "image/gif"),
        (b"RIFF\x24\x00\x00\x00WEBP", "image/webp"),
        (b"RIFF\x24\x00\x00\x00WAVE", None),
        (b'<svg xmlns="', None),
        (b"<html><scrip", None),
        (b"\x89PN", None),
        (b"", None),
    ],
)
def test_image_type(head: bytes, expected: str | None) -> None:
    """Only the four raster formats are recognised, by their signatures alone.

    A sound in the same RIFF container, an SVG, a page and a cut signature are not images.

    Args:
        head: The first bytes of a content.
        expected: The media type it should get.
    """
    assert image_type(head) == expected
