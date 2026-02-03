import asyncio
from PyQt6.QtWidgets import QMainWindow, QToolBar
from PyQt6.QtGui import QKeySequence, QShortcut, QCursor
from PyQt6.QtCore import Qt, QEvent

from .document_viewer import DocumentViewer
from .widgets.zoom_controls import ZoomControls
from ..viewmodels.document_viewmodel import DocumentViewModel
from ..viewmodels.zoom_viewmodel import ZoomViewModel
from ..viewmodels.selection_viewmodel import SelectionViewModel
from ..utils.logging import get_logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Standalone Reader")
        self.resize(1024, 768)

        self._logger = get_logger("MainWindow")

        self.vm = DocumentViewModel()
        self.zoom_vm = ZoomViewModel()
        self.selection_vm = SelectionViewModel()

        self.viewer = DocumentViewer()
        self.setCentralWidget(self.viewer)

        self._setup_zoom_ui()
        self._setup_shortcuts()

        self.vm.document_loaded.connect(self._handle_document_loaded)
        self.vm.page_rendered.connect(self.viewer.update_page_image)
        self.viewer.request_page_render.connect(self._handle_page_request)
        self.viewer.cancel_renders.connect(self.vm.cancel_obsolete_renders)

        self.zoom_vm.zoom_preview_changed.connect(self._handle_zoom_preview)
        self.zoom_vm.zoom_committed.connect(self._handle_zoom_committed)

        self.viewer.selection_started.connect(self.selection_vm.start_selection)
        self.viewer.selection_updated.connect(self.selection_vm.update_selection)
        self.viewer.word_selection_requested.connect(self.selection_vm.select_word_at)
        self.viewer.selection_cleared.connect(self.selection_vm.clear_selection)

        self.selection_vm.selection_changed.connect(self._on_selection_received)

        self.viewer.installEventFilter(self)

    def _setup_zoom_ui(self):
        """Creates and wires the zoom toolbar."""
        toolbar = QToolBar("Zoom")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.zoom_controls = ZoomControls()
        toolbar.addWidget(self.zoom_controls)

        self.zoom_controls.zoom_in_clicked.connect(self.zoom_vm.zoom_in)
        self.zoom_controls.zoom_out_clicked.connect(self.zoom_vm.zoom_out)
        self.zoom_controls.zoom_reset_clicked.connect(self.zoom_vm.reset_zoom)
        self.zoom_controls.preset_selected.connect(self.zoom_vm.set_preset)
        self.zoom_controls.fit_width_requested.connect(self._handle_fit_width)
        self.zoom_controls.fit_page_requested.connect(self._handle_fit_page)

        self._update_zoom_display()

    def _setup_shortcuts(self):
        """Registers keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoom_vm.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self.zoom_vm.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoom_vm.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self.zoom_vm.reset_zoom)

        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(self.selection_vm.clear_selection)

    def _handle_document_loaded(self, page_sizes):
        """Configures viewer layout and registers selection data."""
        self.viewer.load_document_layout(page_sizes)

        for i in range(len(page_sizes)):
            model = self.vm.get_selection_model(i)
            if model:
                self.selection_vm.register_page_model(i, model)
                self.viewer.update_overlay_data(
                    i,
                    model._characters,
                    self.zoom_vm.get_zoom(),
                )

    def _on_selection_received(self, text: str):
        """Handles processed selection updates."""
        active_page = self.selection_vm._active_page
        bboxes = self.selection_vm.get_selection_bboxes(active_page)
        self.viewer.set_selection_highlights(active_page, bboxes)

        if text:
            self._logger.info(f"Selection Captured: '{text}'")

    def _handle_fit_width(self):
        zoom = self.viewer.calculate_fit_zoom("width")
        self.zoom_vm.set_fit_width(zoom)

    def _handle_fit_page(self):
        zoom = self.viewer.calculate_fit_zoom("page")
        self.zoom_vm.set_fit_page(zoom)

    def _handle_zoom_preview(self, zoom_level: int):
        self.viewer.handle_zoom_preview(zoom_level)
        self._update_zoom_display()

    def _handle_zoom_committed(self, zoom_level: int):
        self.vm.set_zoom(zoom_level)
        self.viewer.handle_zoom_committed(zoom_level)

        for i in range(self.vm._parser.get_page_count()):
            model = self.vm.get_selection_model(i)
            if model:
                self.viewer.update_overlay_data(
                    i,
                    model._characters,
                    zoom_level,
                )

    def _update_zoom_display(self):
        zoom_level = self.zoom_vm.get_zoom()
        mode = self.zoom_vm.get_mode()
        is_fit_mode = mode in [
            ZoomViewModel.FIT_WIDTH,
            ZoomViewModel.FIT_PAGE,
        ]
        label = (
            "Fit Width"
            if mode == ZoomViewModel.FIT_WIDTH
            else "Fit Page"
            if mode == ZoomViewModel.FIT_PAGE
            else ""
        )
        self.zoom_controls.update_zoom_display(
            zoom_level,
            is_fit_mode,
            label,
        )

    def _handle_page_request(self, page_index: int, zoom_level: int):
        asyncio.create_task(
            self.vm.request_page(page_index, zoom_level)
        )

    def load_file(self, file_path: str):
        """Loads a document."""
        self.vm.load_document(file_path)

    def eventFilter(self, obj, event):
        """Handles Ctrl+Scroll zooming."""
        if obj == self.viewer and event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._handle_scroll_zoom(event)
                return True
        return super().eventFilter(obj, event)

    def _handle_scroll_zoom(self, wheel_event):
        """Applies zoom centered on cursor position."""
        scroll_area = self.viewer._scroll_area
        scroll_bar = scroll_area.verticalScrollBar()
        old_scroll = scroll_bar.value()

        cursor_pos = scroll_area.viewport().mapFromGlobal(QCursor.pos())
        doc_y_before = old_scroll + cursor_pos.y()

        old_zoom = self.zoom_vm.get_zoom()
        delta = wheel_event.angleDelta().y()
        new_zoom = int(old_zoom + (delta / 120.0) * 10)
        new_zoom = max(
            ZoomViewModel.MIN_ZOOM,
            min(ZoomViewModel.MAX_ZOOM, new_zoom),
        )

        self.zoom_vm.set_zoom(new_zoom)

        if old_zoom > 0:
            zoom_ratio = new_zoom / old_zoom
            new_scroll = int(
                doc_y_before * zoom_ratio - cursor_pos.y()
            )
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(
                0,
                lambda: scroll_bar.setValue(new_scroll),
            )
