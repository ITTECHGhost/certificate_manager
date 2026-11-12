import io

import pytest
from PIL import Image

from services.order_images import file_to_pages


def _png(w=3000, h=2000):
    b = io.BytesIO()
    Image.new("RGBA", (w, h), (200, 10, 10, 255)).save(b, "PNG")
    return b.getvalue()


def test_photo_becomes_small_jpeg_and_thumb():
    [(page, thumb)] = file_to_pages("scan.PNG", _png())
    assert page[:3] == b"\xff\xd8\xff" and thumb[:3] == b"\xff\xd8\xff"
    assert max(Image.open(io.BytesIO(page)).size) <= 2200
    assert max(Image.open(io.BytesIO(thumb)).size) <= 260


def test_pdf_is_split_into_pages():
    b = io.BytesIO()
    imgs = [Image.new("RGB", (600, 800), "white") for _ in range(3)]
    imgs[0].save(b, "PDF", save_all=True, append_images=imgs[1:])
    assert len(file_to_pages("order.pdf", b.getvalue())) == 3


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        file_to_pages("a.docx", b"x")
