import asyncio
from PyQt6.QtWidgets import QMainWindow, QToolBar, QApplication
from PyQt6.QtGui import QKeySequence, QShortcut, QCursor
from PyQt6.QtCore import Qt, QEvent, QRectF

from .document_viewer import DocumentViewer
from .widgets.zoom_controls import ZoomControls
from .widgets.translation_popup import TranslationPopup
from ..viewmodels.document_viewmodel import DocumentViewModel
from ..viewmodels.zoom_viewmodel import ZoomViewModel
from ..viewmodels.selection_viewmodel import SelectionViewModel
from ..viewmodels.translation_viewmodel import TranslationViewModel
from ..utils.logging import get_logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Standalone Reader")
        self.resize(1024, 768)

        self._logger = get_logger("MainWindow")

        # --- ViewModels ---
        self.vm = DocumentViewModel()
        self.zoom_vm = ZoomViewModel()
        self.selection_vm = SelectionViewModel()
        self.translation_vm = TranslationViewModel()

        # --- Central Widget ---
        self.viewer = DocumentViewer()
        self.setCentralWidget(self.viewer)

        # --- Popup ---
        self.popup = TranslationPopup(self)
        self.popup.hide()

        # --- UI Setup ---
        self._setup_zoom_ui()
        self._setup_shortcuts()

        # --- Connections: Document ---
        self.vm.document_loaded.connect(self._handle_document_loaded)
        self.vm.page_rendered.connect(self.viewer.update_page_image)
        self.viewer.request_page_render.connect(self._handle_page_request)
        self.viewer.cancel_renders.connect(self.vm.cancel_obsolete_renders)

        # --- Connections: Zoom ---
        self.zoom_vm.zoom_preview_changed.connect(self._handle_zoom_preview)
        self.zoom_vm.zoom_committed.connect(self._handle_zoom_committed)

        # --- Connections: Selection ---
        self.viewer.selection_started.connect(self.selection_vm.start_selection)
        self.viewer.selection_updated.connect(self.selection_vm.update_selection)
        self.viewer.word_selection_requested.connect(self.selection_vm.select_word_at)
        
        self.viewer.selection_cleared.connect(self._handle_selection_cleared)
        self.popup.dismissed.connect(self._handle_popup_dismissed)

        self.selection_vm.selection_changed.connect(self._on_selection_received)

        # --- Connections: Translation (Level 3) ---
        self.translation_vm.lookup_success.connect(self.popup.show_result)
        self.translation_vm.lookup_failed.connect(self._handle_lookup_error)

        # --- Event Filters ---
        self.viewer.installEventFilter(self)

    def _setup_zoom_ui(self):
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
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoom_vm.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self.zoom_vm.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoom_vm.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self.zoom_vm.reset_zoom)

        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(self._handle_selection_cleared)

    # --- Handlers ---

    def _handle_document_loaded(self, page_sizes):
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

    def _handle_selection_cleared(self):
        """Clears selection logic and hides UI."""
        self.selection_vm.clear_selection()
        self.popup.close()

    def _handle_popup_dismissed(self):
        """Called when popup closes itself (Esc/Click-out)."""
        self.selection_vm.clear_selection()

    def _on_selection_received(self, text: str):
        """Handles processed selection updates."""
        active_page = self.selection_vm._active_page
        bboxes = self.selection_vm.get_selection_bboxes(active_page)
        self.viewer.set_selection_highlights(active_page, bboxes)

        if not text.strip():
            self.popup.hide()
            return

        self._logger.info(f"Selection Captured: '{text}'")

        # 1. Position and Show Loading (UX Priority)
        self._position_and_show_popup(active_page, bboxes, text)
        
        # 2. Trigger Async Lookup
        asyncio.create_task(self.translation_vm.lookup(text))

    def _handle_lookup_error(self, msg: str):
        """Wraps error messages into a safe dict structure for the UI."""
        error_data = {
            "word": "Lookup Failed",
            "phonetic": "",
            "definitions": [
                {"pos": "system", "text": msg}
            ]
        }
        self.popup.show_result(error_data)

    def _position_and_show_popup(self, page_index: int, bboxes: list[QRectF], text: str):
        """Smart positioning logic: Map -> Clamp -> Flip."""
        if page_index not in self.viewer._pages:
            return

        page_widget = self.viewer._pages[page_index]
        if not bboxes:
            return
        
        # 1. Calculate Union Rect (Selection Bounds in Points)
        union_rect = bboxes[0]
        for r in bboxes[1:]:
            union_rect = union_rect.united(r)

        # 2. Scale to Current Zoom
        scale = self.zoom_vm.get_zoom() / 100.0
        widget_rect = QRectF(
            union_rect.x() * scale,
            union_rect.y() * scale,
            union_rect.width() * scale,
            union_rect.height() * scale
        )

        # 3. Map to Global Screen Coordinates
        top_left_global = page_widget.mapToGlobal(widget_rect.topLeft().toPoint())
        bottom_left_global = page_widget.mapToGlobal(widget_rect.bottomLeft().toPoint())
        
        # 4. Get Screen Geometry constraints
        screen_geo = self.screen().availableGeometry()
        
        # Force size calculation if hidden (estimate or actual)
        popup_width = 440 # Matches CSS width in popup
        popup_height = self.popup.sizeHint().height() or 200

        # 5. Vertical Logic (Flip Strategy)
        # Default: Place below the text
        target_y = bottom_left_global.y() + 8 
        
        # Check if it hits the bottom of the screen
        if target_y + popup_height > screen_geo.bottom() - 20:
            # FLIP: Place above the text
            target_y = top_left_global.y() - popup_height - 8

        # 6. Horizontal Logic (Clamp Strategy)
        target_x = bottom_left_global.x()
        
        # Check right edge
        if target_x + popup_width > screen_geo.right() - 20:
            target_x = screen_geo.right() - popup_width - 20
            
        # Check left edge
        target_x = max(screen_geo.left() + 10, target_x)

        # 7. Apply
        self.popup.move(int(target_x), int(target_y))
        self.popup.show_loading(text)

    # --- Zoom Handlers ---

    def _handle_fit_width(self):
        zoom = self.viewer.calculate_fit_zoom("width")
        self.zoom_vm.set_fit_width(zoom)

    def _handle_fit_page(self):
        zoom = self.viewer.calculate_fit_zoom("page")
        self.zoom_vm.set_fit_page(zoom)

    def _handle_zoom_preview(self, zoom_level: int):
        self.viewer.handle_zoom_preview(zoom_level)
        self._update_zoom_display()
        self.popup.hide() # Hide popup during zoom operations

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

    # --- File Loading ---

    def load_file(self, file_path: str):
        self.vm.load_document(file_path)

    # --- Event Filter (Ctrl+Scroll) ---

    def eventFilter(self, obj, event):
        if obj == self.viewer and event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._handle_scroll_zoom(event)
                return True
        return super().eventFilter(obj, event)

    def _handle_scroll_zoom(self, wheel_event):
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