import math
from typing import List, Optional
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QBrush, QColor, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from ...models.selection.selection_model import CharMetadata


class TextOverlay(QWidget):
    selection_started = pyqtSignal(int)
    selection_updated = pyqtSignal(int)
    word_selection_requested = pyqtSignal(int)
    selection_cleared = pyqtSignal()

    MAGNETIC_THRESHOLD = 15.0

    def __init__(self, page_index: int, parent=None):
        super().__init__(parent)
        self._page_index = page_index

        self._bboxes: List[CharMetadata] = []
        self._highlight_rects: List[QRectF] = []

        self._display_zoom = 100

        self._drag_start_pos: Optional[QPointF] = None
        self._pending_start_idx: Optional[int] = None
        self._is_dragging = False

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

    def update_data(self, bboxes: List[CharMetadata], zoom: int):
        self._bboxes = bboxes
        self._display_zoom = zoom
        self.update()

    def set_highlight_rects(self, rects: List[QRectF]):
        self._highlight_rects = rects
        self.update()

    def _ui_to_pdf_point(self, pos: QPointF) -> QPointF:
        scale = 100.0 / self._display_zoom
        return QPointF(pos.x() * scale, pos.y() * scale)

    def _get_char_index_at(self, pos: QPointF) -> Optional[int]:
        pdf_pos = self._ui_to_pdf_point(pos)
        closest_idx = None
        min_dist = float("inf")
        pdf_threshold = self.MAGNETIC_THRESHOLD / (self._display_zoom / 100.0)

        for i, item in enumerate(self._bboxes):
            rect = item.bbox
            if rect.contains(pdf_pos):
                return i

            center = rect.center()
            dist = math.hypot(
                pdf_pos.x() - center.x(),
                pdf_pos.y() - center.y(),
            )

            if dist < min_dist and dist < pdf_threshold:
                min_dist = dist
                closest_idx = i

        return closest_idx

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_cleared.emit()

            idx = self._get_char_index_at(event.position())
            if idx is not None:
                self._drag_start_pos = event.position()
                self._pending_start_idx = idx
                self._is_dragging = False
            else:
                self._drag_start_pos = None
                self._pending_start_idx = None

    def mouseMoveEvent(self, event):
        if (
            self._pending_start_idx is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            if not self._is_dragging:
                drag_dist = (
                    event.position() - self._drag_start_pos
                ).manhattanLength()
                if drag_dist > QApplication.startDragDistance():
                    self._is_dragging = True
                    self.selection_started.emit(self._pending_start_idx)

            if self._is_dragging:
                idx = self._get_char_index_at(event.position())
                if idx is not None:
                    self.selection_updated.emit(idx)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._pending_start_idx = None
        self._is_dragging = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._get_char_index_at(event.position())
            if idx is not None:
                self.word_selection_requested.emit(idx)

    def _merge_rects(self, rects: List[QRectF]) -> List[QRectF]:
        if not rects:
            return []

        sorted_rects = sorted(
            rects,
            key=lambda r: (int(r.center().y() / 10), r.x()),
        )

        merged = []
        current_rect = sorted_rects[0]

        for next_rect in sorted_rects[1:]:
            vertical_aligned = (
                abs(current_rect.center().y() - next_rect.center().y()) < 5
            )
            horizontal_touching = (
                next_rect.left() < current_rect.right() + 4
            )

            if vertical_aligned and horizontal_touching:
                current_rect = current_rect.united(next_rect)
            else:
                merged.append(current_rect)
                current_rect = next_rect

        merged.append(current_rect)
        return merged

    def paintEvent(self, event):
        if not self._highlight_rects:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        highlight_color = QColor(0, 122, 255, 75)
        painter.setBrush(QBrush(highlight_color))
        painter.setPen(Qt.PenStyle.NoPen)

        scale = self._display_zoom / 100.0

        ui_rects = [
            QRectF(
                r.x() * scale,
                r.y() * scale,
                r.width() * scale,
                r.height() * scale,
            )
            for r in self._highlight_rects
        ]

        solid_blocks = self._merge_rects(ui_rects)

        path = QPainterPath()
        for rect in solid_blocks:
            path.addRoundedRect(
                rect.adjusted(0, 1, 0, -1),
                3,
                3,
            )

        painter.drawPath(path)
        painter.end()
