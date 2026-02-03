from abc import ABC, abstractmethod
from typing import Optional, List, Dict

class Document(ABC):
    """
    Abstract Interface for all document types (PDF, EPUB).
    Strictly read-only APIs.
    """

    @abstractmethod
    def load(self, file_path: str) -> None:
        """Validates and opens the file handle."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, str]:
        """Returns {'title': ..., 'author': ...}."""
        pass

    @abstractmethod
    def get_page_count(self) -> int:
        pass

    @abstractmethod
    def get_page_size(self, page_index: int) -> tuple[int, int]:
        """Returns (width, height) of the page in points (72 DPI)."""
        pass

    @abstractmethod
    def get_page_text(self, page_index: int) -> str:
        """
        Returns the raw text of a specific page.
        """
        pass
    
    @abstractmethod
    def render_page(self, page_index: int, zoom_level: int = 100):
        """
        Returns a QImage of the page.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        pass