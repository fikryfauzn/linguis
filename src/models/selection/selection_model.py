from dataclasses import dataclass
from typing import List, Optional
from PyQt6.QtCore import QRectF


@dataclass
class CharMetadata:
    """Represents a single character and its bounding box."""
    char: str
    bbox: QRectF


class SelectionModel:
    """Text-domain model for a single page."""
    def __init__(self, page_index: int):
        self.page_index = page_index
        self._characters: List[CharMetadata] = []

    def set_characters(self, characters: List[CharMetadata]):
        """Sets character metadata for the page."""
        self._characters = characters

    def get_char_at(self, point: QRectF) -> Optional[int]:
        """Returns the index of the character containing the point."""
        for i, meta in enumerate(self._characters):
            if meta.bbox.contains(point):
                return i
        return None

    def get_text_range(self, start_idx: int, end_idx: int) -> str:
        """Returns the concatenated text between two indices."""
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        start_idx = max(0, start_idx)
        end_idx = min(len(self._characters) - 1, end_idx)

        return "".join(c.char for c in self._characters[start_idx:end_idx + 1])

    def get_bboxes_for_range(self, start_idx: int, end_idx: int) -> List[QRectF]:
        """Returns bounding boxes for a character range."""
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        return [c.bbox for c in self._characters[start_idx:end_idx + 1]]

    @property
    def char_count(self) -> int:
        return len(self._characters)
