from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout
from PyQt6.QtGui import QImage, QPainter, QPaintEvent
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QEvent
from collections import OrderedDict
from .widgets.text_overlay import TextOverlay


class PageWidget(QWidget):
    """Renders a single page image and hosts the selection overlay."""
    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self._image: QImage | None = None
        self._is_loaded = False
        self._is_rendering = False
        self._original_size = (0, 0)

        self._render_zoom = 100
        self._display_zoom = 100

        self.overlay = TextOverlay(self.index, self)

        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #DDDDDD; border: 1px solid #999;")

    def set_placeholder_size(self, width: int, height: int):
        """Sets widget size before image load."""
        self._original_size = (width, height)
        self.setFixedSize(width, height)
        self.overlay.resize(self.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(self.size())

    def set_image(self, image: QImage, render_zoom: int):
        """Sets rendered page image."""
        self._image = image
        self._render_zoom = render_zoom
        self._is_loaded = True
        self._is_rendering = False
        self.setStyleSheet("background-color: white; border: none;")
        self.update()

    def set_display_zoom(self, zoom: int):
        """Updates widget size for display zoom."""
        if zoom != self._display_zoom:
            self._display_zoom = zoom
            base_w, base_h = self._original_size
            scale = zoom / 100.0
            self.setFixedSize(int(base_w * scale), int(base_h * scale))
            self.update()

    def is_loaded(self) -> bool:
        return self._is_loaded

    def is_rendering(self) -> bool:
        return self._is_rendering

    def needs_rerender(self) -> bool:
        """Checks if render zoom differs significantly from display zoom."""
        return self._is_loaded and abs(self._display_zoom - self._render_zoom) > 5

    def mark_rendering(self):
        self._is_rendering = True

    def unload_image(self):
        """Releases page image memory."""
        self._image = None
        self._is_loaded = False
        self._is_rendering = False
        self._render_zoom = 100
        self.setStyleSheet("background-color: #DDDDDD; border: 1px solid #999;")
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        if self._image:
            scale_factor = (
                self._display_zoom / self._render_zoom
                if self._render_zoom > 0
                else 1.0
            )

            if abs(scale_factor - 1.0) < 0.01:
                painter.drawImage(0, 0, self._image)
            else:
                painter.scale(scale_factor, scale_factor)
                painter.drawImage(0, 0, self._image)
        else:
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Page {self.index + 1}",
            )
        painter.end()


class DocumentViewer(QWidget):
    """Scrollable container managing page widgets and rendering."""
    request_page_render = pyqtSignal(int, int)
    cancel_renders = pyqtSignal(set)

    selection_started = pyqtSignal(int, int)
    selection_updated = pyqtSignal(int)
    selection_cleared = pyqtSignal()
    word_selection_requested = pyqtSignal(int, int)

    LOOKAHEAD_PAGES = 3
    MAX_CACHED_PAGES = 12

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(20, 20, 20, 20)
        self._container_layout.setSpacing(10)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._scroll_area.setWidget(self._container)
        self._layout.addWidget(self._scroll_area)

        self._scroll_area.viewport().installEventFilter(self)

        self._pages: dict[int, PageWidget] = {}
        self._total_pages = 0
        self._loaded_pages: OrderedDict[int, bool] = OrderedDict()
        self._current_render_range: set[int] = set()

        self._base_page_sizes: list[tuple[int, int]] = []
        self._display_zoom = 100
        self._committed_zoom = 100

        self._scroll_bar = self._scroll_area.verticalScrollBar()
        self._scroll_bar.valueChanged.connect(self._check_visibility)

    def eventFilter(self, source, event):
        if (
            source == self._scroll_area.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            self.selection_cleared.emit()

        return super().eventFilter(source, event)

    def load_document_layout(self, page_sizes: list[tuple[int, int]]):
        """Creates page widgets from document layout."""
        self._pages.clear()
        self._loaded_pages.clear()
        self._base_page_sizes = page_sizes
        self._total_pages = len(page_sizes)

        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, (w, h) in enumerate(page_sizes):
            page = PageWidget(idx)
            page.set_placeholder_size(w, h)

            page.overlay.selection_started.connect(
                lambda char_idx, p_idx=idx: self.selection_started.emit(
                    p_idx, char_idx
                )
            )

            page.overlay.selection_updated.connect(
                self.selection_updated.emit
            )

            page.overlay.word_selection_requested.connect(
                lambda char_idx, p_idx=idx: self.word_selection_requested.emit(
                    p_idx, char_idx
                )
            )

            page.overlay.selection_cleared.connect(
                self.selection_cleared.emit
            )

            self._container_layout.addWidget(page)
            self._pages[idx] = page

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._check_visibility)

    def update_overlay_data(self, page_index: int, bboxes: list, zoom: int):
        if page_index in self._pages:
            self._pages[page_index].overlay.update_data(bboxes, zoom)

    def set_selection_highlights(self, page_index: int, rects: list):
        for p in self._pages.values():
            p.overlay.set_highlight_rects([])

        if page_index in self._pages:
            self._pages[page_index].overlay.set_highlight_rects(rects)

    def handle_zoom_preview(self, zoom_level: int):
        self._display_zoom = zoom_level
        for page in self._pages.values():
            page.set_display_zoom(zoom_level)
            page.overlay.update_data(page.overlay._bboxes, zoom_level)

    def handle_zoom_committed(self, zoom_level: int):
        self._committed_zoom = zoom_level

        for page in self._pages.values():
            if page.is_loaded() and page.needs_rerender():
                page.unload_image()

        self._loaded_pages.clear()
        self._current_render_range.clear()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self._check_visibility)

    def update_page_image(self, page_index: int, image: QImage, render_zoom: int):
        if page_index in self._pages:
            self._pages[page_index].set_image(image, render_zoom)

            if page_index in self._loaded_pages:
                self._loaded_pages.move_to_end(page_index)
            else:
                self._loaded_pages[page_index] = True

            self._current_render_range.discard(page_index)
            self._evict_old_pages()

    def _evict_old_pages(self):
        while len(self._loaded_pages) > self.MAX_CACHED_PAGES:
            oldest_index, _ = self._loaded_pages.popitem(last=False)
            if oldest_index in self._pages:
                self._pages[oldest_index].unload_image()

    def _check_visibility(self):
        scroll_y = self._scroll_bar.value()
        viewport_height = self._scroll_area.viewport().height()
        viewport_rect = QRect(
            0,
            scroll_y,
            self._container.width(),
            viewport_height,
        )

        visible_indices = [
            index
            for index, page in self._pages.items()
            if page.geometry().intersects(viewport_rect)
        ]

        if not visible_indices:
            return

        min_visible = min(visible_indices)
        max_visible = max(visible_indices)

        render_start = max(0, min_visible - self.LOOKAHEAD_PAGES)
        render_end = min(
            self._total_pages - 1,
            max_visible + self.LOOKAHEAD_PAGES,
        )

        new_render_range = set(range(render_start, render_end + 1))
        self.cancel_renders.emit(new_render_range)

        pages_to_request = []

        for index in new_render_range:
            page = self._pages[index]
            if (
                not page.is_loaded()
                and not page.is_rendering()
            ) or page.needs_rerender():
                pages_to_request.append(index)
                page.mark_rendering()

        self._current_render_range = new_render_range

        viewport_center = (min_visible + max_visible) / 2
        pages_to_request.sort(
            key=lambda idx: abs(idx - viewport_center)
        )

        for index in pages_to_request:
            self.request_page_render.emit(
                index,
                self._committed_zoom,
            )

    def calculate_fit_zoom(self, mode: str) -> int:
        if not self._base_page_sizes or not self._pages:
            return 100

        viewport_width = self._scroll_area.viewport().width()
        viewport_height = self._scroll_area.viewport().height()
        available_width = viewport_width - 40
        available_height = viewport_height - 40

        base_page_width, base_page_height = self._base_page_sizes[0]

        if mode == "width":
            zoom = int((available_width / base_page_width) * 100)
        elif mode == "page":
            width_ratio = available_width / base_page_width
            height_ratio = available_height / base_page_height
            zoom = int(min(width_ratio, height_ratio) * 100)
        else:
            zoom = 100

        return max(25, min(400, zoom))
