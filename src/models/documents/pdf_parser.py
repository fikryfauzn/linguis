import fitz
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QRectF
from typing import List, Tuple

from .document import Document
from ..selection.selection_model import CharMetadata


class PdfParser(Document):
    def __init__(self):
        self._doc: fitz.Document | None = None

    def load(self, path: str):
        """Loads a PDF file."""
        try:
            self._doc = fitz.open(path)
        except Exception as e:
            print(f"Error loading PDF: {e}")
            self._doc = None

    def close(self):
        """Closes the document."""
        if self._doc:
            self._doc.close()
            self._doc = None

    def get_metadata(self) -> dict:
        """Returns PDF metadata."""
        return self._doc.metadata if self._doc else {}

    def get_page_count(self) -> int:
        """Returns the number of pages."""
        return len(self._doc) if self._doc else 0

    def get_page_size(self, page_index: int, zoom_level: int = 100) -> Tuple[int, int]:
        """Returns page size in pixels at the given zoom level."""
        if not self._doc:
            return 0, 0

        page = self._doc[page_index]
        scale = zoom_level / 100.0
        return int(page.rect.width * scale), int(page.rect.height * scale)

    def get_page_text(self, page_index: int) -> str:
        """Returns raw page text."""
        if not self._doc:
            return ""
        return self._doc[page_index].get_text()

    def render_page(self, page_index: int, zoom_level: int = 100) -> QImage | None:
        """Renders a page to a QImage."""
        if not self._doc:
            return None

        page = self._doc[page_index]
        scale = zoom_level / 100.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))

        img_format = (
            QImage.Format.Format_RGB888
            if pix.n == 3
            else QImage.Format.Format_RGBA8888
        )

        qimg = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            img_format,
        )

        return qimg.copy()

    def get_character_map(self, page_index: int) -> List[CharMetadata]:
        """Returns a list of characters with bounding boxes."""
        if not self._doc:
            return []

        page = self._doc[page_index]
        text_data = page.get_text("rawdict")

        chars: List[CharMetadata] = []

        for block in text_data["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for char_info in span.get("chars", []):
                        x0, y0, x1, y1 = char_info["bbox"]
                        bbox = QRectF(x0, y0, x1 - x0, y1 - y0)
                        chars.append(
                            CharMetadata(
                                char=char_info["c"],
                                bbox=bbox,
                            )
                        )

        return chars
