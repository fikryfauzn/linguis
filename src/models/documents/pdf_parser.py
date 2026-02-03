import logging
from pathlib import Path
from typing import Dict, Optional
from pypdf import PdfReader
from pdf2image import convert_from_path
from PIL.ImageQt import ImageQt
from PyQt6.QtGui import QImage
from .document import Document
from ...utils.logging import get_logger, sanitize_for_log

class PdfParser(Document):
    """
    Handles both text extraction (via pypdf) and visual rendering (via pdf2image).
    """
    def __init__(self):
        self._logger = get_logger("PdfParser")
        self._reader: Optional[PdfReader] = None
        self._file_path: Optional[str] = None
        self._page_count: int = 0

    def load(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            self._logger.error(f"File not found: {sanitize_for_log(file_path)}")
            raise FileNotFoundError("File does not exist")
        
        try:
            self._reader = PdfReader(str(path))
            self._file_path = str(path)
            self._page_count = len(self._reader.pages)
            self._logger.info(f"PDF loaded. Pages: {self._page_count}")
        except Exception as e:
            self._logger.error(f"Failed to load PDF: {e}")
            raise ValueError("Corrupt or unsupported PDF")

    def get_metadata(self) -> Dict[str, str]:
        if not self._reader:
            return {}
        
        meta = self._reader.metadata
        if not meta:
            return {"title": "Unknown", "author": "Unknown"}
        
        return {
            "title": meta.title or "Unknown",
            "author": meta.author or "Unknown"
        }

    def get_page_count(self) -> int:
        return self._page_count

    def get_page_size(self, page_index: int, zoom_level: int = 100) -> tuple[int, int]:
        """
        Returns page dimensions scaled by zoom level.
        zoom_level: 50-400 (percentage)
        """
        if not self._reader:
            return (0, 0)
        
        try:
            box = self._reader.pages[page_index].mediabox
            base_width = int(box.width)
            base_height = int(box.height)
            
            # Apply zoom scaling
            scale = zoom_level / 100.0
            return (int(base_width * scale), int(base_height * scale))
        except Exception:
            return (0, 0)

    def get_page_text(self, page_index: int) -> str:
        if not self._reader or page_index < 0 or page_index >= self._page_count:
            return ""
        
        try:
            page = self._reader.pages[page_index]
            text = page.extract_text()
            return text if text else ""
        except Exception as e:
            self._logger.warning(f"Failed to extract text from page {page_index}: {e}")
            return ""

    def render_page(self, page_index: int, zoom_level: int = 100) -> Optional[QImage]:
        """
        Renders a specific page to a QImage at the specified zoom level.
        
        zoom_level: 50-400 (percentage)
        - 100 = native resolution (72 DPI)
        - 200 = 2x scaling (144 DPI)
        - 50 = half resolution (36 DPI)
        """
        if not self._file_path:
            return None
        
        try:
            # Calculate DPI based on zoom
            # Base DPI is 72, scale proportionally
            target_dpi = int(72 * (zoom_level / 100.0))
            
            # Clamp DPI to reasonable bounds to prevent memory issues
            # 36 DPI (50%) to 288 DPI (400%)
            target_dpi = max(36, min(288, target_dpi))
            
            images = convert_from_path(
                self._file_path,
                first_page=page_index + 1,
                last_page=page_index + 1,
                dpi=target_dpi
            )
            
            if not images:
                return None
            
            pil_image = images[0]
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            
            return ImageQt(pil_image).copy()
            
        except Exception as e:
            self._logger.error(f"Failed to render page {page_index} at {zoom_level}%: {e}")
            return None

    def close(self) -> None:
        self._reader = None
        self._file_path = None