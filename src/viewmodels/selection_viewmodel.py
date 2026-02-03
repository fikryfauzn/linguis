import re
from typing import Optional, List, Dict
from PyQt6.QtCore import QObject, pyqtSignal, QRectF
from ..models.selection.selection_model import SelectionModel


class SelectionViewModel(QObject):
    """Manages text selection logic across the document."""
    selection_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._page_models: Dict[int, SelectionModel] = {}
        self._active_page: Optional[int] = None

        self._start_idx: Optional[int] = None
        self._end_idx: Optional[int] = None

    def register_page_model(self, page_index: int, model: SelectionModel):
        self._page_models[page_index] = model

    def start_selection(self, page_index: int, char_index: int):
        self._active_page = page_index
        self._start_idx = char_index
        self._end_idx = char_index

    def update_selection(self, char_index: int):
        if self._start_idx is not None:
            self._end_idx = char_index
            self._emit_current_selection()

    def select_word_at(self, page_index: int, char_index: int):
        """Expands a character index into a word selection."""
        model = self._page_models.get(page_index)
        if not model:
            return

        chars = model._characters
        if not (0 <= char_index < len(chars)):
            return

        def is_word_char(c: str) -> bool:
            return c.isalnum() or c in "_-'"

        SPACE_THRESHOLD = 4.0
        LINE_THRESHOLD = 5.0

        if not is_word_char(chars[char_index].char):
            self.start_selection(page_index, char_index)
            self.update_selection(char_index)
            return

        start = char_index
        end = char_index

        while start > 0:
            curr = chars[start]
            prev = chars[start - 1]

            gap = curr.bbox.left() - prev.bbox.right()
            v_gap = abs(curr.bbox.top() - prev.bbox.top())

            if (
                not is_word_char(prev.char)
                or gap > SPACE_THRESHOLD
                or v_gap > LINE_THRESHOLD
            ):
                break
            start -= 1

        while end < len(chars) - 1:
            curr = chars[end]
            next_char = chars[end + 1]

            gap = next_char.bbox.left() - curr.bbox.right()
            v_gap = abs(next_char.bbox.top() - curr.bbox.top())

            if (
                not is_word_char(next_char.char)
                or gap > SPACE_THRESHOLD
                or v_gap > LINE_THRESHOLD
            ):
                break
            end += 1

        self.start_selection(page_index, start)
        self.update_selection(end)

    def _emit_current_selection(self):
        if (
            self._active_page is None
            or self._start_idx is None
            or self._end_idx is None
        ):
            return

        model = self._page_models.get(self._active_page)
        if not model:
            return

        raw_text = model.get_text_range(self._start_idx, self._end_idx)
        processed_text = self.merge_hyphens(raw_text)
        self.selection_changed.emit(processed_text)

    def merge_hyphens(self, text: str) -> str:
        return re.sub(r"-\n([a-zA-Z])", r"\1", text)

    def get_selection_bboxes(self, page_index: int) -> List[QRectF]:
        if page_index != self._active_page or self._start_idx is None:
            return []

        model = self._page_models.get(page_index)
        return (
            model.get_bboxes_for_range(self._start_idx, self._end_idx)
            if model
            else []
        )

    def clear_selection(self):
        self._active_page = None
        self._start_idx = None
        self._end_idx = None
        self.selection_changed.emit("")
