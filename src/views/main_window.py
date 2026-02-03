import asyncio
from PyQt6.QtWidgets import QMainWindow, QToolBar
from PyQt6.QtGui import QKeySequence, QShortcut, QCursor
from PyQt6.QtCore import Qt, QEvent
from .document_viewer import DocumentViewer
from .widgets.zoom_controls import ZoomControls
from ..viewmodels.document_viewmodel import DocumentViewModel
from ..viewmodels.zoom_viewmodel import ZoomViewModel
from ..utils.logging import get_logger

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Standalone Reader")
        self.resize(1024, 768)
        
        self._logger = get_logger("MainWindow")
        
        # Initialize ViewModels
        self.vm = DocumentViewModel()
        self.zoom_vm = ZoomViewModel()
        
        # Initialize View
        self.viewer = DocumentViewer()
        self.setCentralWidget(self.viewer)
        
        # Setup zoom controls toolbar
        self._setup_zoom_ui()
        
        # Setup keyboard shortcuts
        self._setup_shortcuts()
        
        # Wiring: Document ViewModel <-> Viewer
        self.vm.document_loaded.connect(self.viewer.load_document_layout)
        self.vm.page_rendered.connect(self.viewer.update_page_image)
        self.viewer.request_page_render.connect(self._handle_page_request)
        self.viewer.cancel_renders.connect(self.vm.cancel_obsolete_renders)
        
        # Wiring: Zoom ViewModel <-> Viewer (Split signals)
        self.zoom_vm.zoom_preview_changed.connect(self._handle_zoom_preview)
        self.zoom_vm.zoom_committed.connect(self._handle_zoom_committed)
        
        # Install event filter for Ctrl+Wheel zoom
        self.viewer.installEventFilter(self)

    def _setup_zoom_ui(self):
        """Create zoom controls toolbar."""
        toolbar = QToolBar("Zoom")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        self.zoom_controls = ZoomControls()
        toolbar.addWidget(self.zoom_controls)
        
        # Wire zoom control buttons
        self.zoom_controls.zoom_in_clicked.connect(self.zoom_vm.zoom_in)
        self.zoom_controls.zoom_out_clicked.connect(self.zoom_vm.zoom_out)
        self.zoom_controls.zoom_reset_clicked.connect(self.zoom_vm.reset_zoom)
        
        # Wire preset selection
        self.zoom_controls.preset_selected.connect(self.zoom_vm.set_preset)
        
        # NEW: Wire fit mode requests
        self.zoom_controls.fit_width_requested.connect(self._handle_fit_width)
        self.zoom_controls.fit_page_requested.connect(self._handle_fit_page)
        
        # Initialize display
        self._update_zoom_display()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for zoom."""
        zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        zoom_in_shortcut.activated.connect(self.zoom_vm.zoom_in)
        
        zoom_in_shortcut2 = QShortcut(QKeySequence("Ctrl+="), self)
        zoom_in_shortcut2.activated.connect(self.zoom_vm.zoom_in)
        
        zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        zoom_out_shortcut.activated.connect(self.zoom_vm.zoom_out)
        
        zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        zoom_reset_shortcut.activated.connect(self.zoom_vm.reset_zoom)

    def _handle_fit_width(self):
        """Calculate and apply fit-width zoom."""
        zoom = self.viewer.calculate_fit_zoom("width")
        self.zoom_vm.set_fit_width(zoom)
    
    def _handle_fit_page(self):
        """Calculate and apply fit-page zoom."""
        zoom = self.viewer.calculate_fit_zoom("page")
        self.zoom_vm.set_fit_page(zoom)
    
    def _handle_zoom_preview(self, zoom_level: int):
        """Handle zoom preview changes."""
        self.viewer.handle_zoom_preview(zoom_level)
        self._update_zoom_display()
    
    def _update_zoom_display(self):
        """Update zoom controls display based on current mode."""
        zoom_level = self.zoom_vm.get_zoom()
        mode = self.zoom_vm.get_mode()
        
        if mode == ZoomViewModel.FIT_WIDTH:
            self.zoom_controls.update_zoom_display(zoom_level, True, "Fit Width")
        elif mode == ZoomViewModel.FIT_PAGE:
            self.zoom_controls.update_zoom_display(zoom_level, True, "Fit Page")
        else:
            self.zoom_controls.update_zoom_display(zoom_level, False)

    def eventFilter(self, obj, event):
        """Handle Ctrl+Wheel zoom with smooth continuous scaling."""
        
        if obj == self.viewer and event.type() == QEvent.Type.Wheel:
            wheel_event = event
            if wheel_event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                scroll_area = self.viewer._scroll_area
                scroll_bar = scroll_area.verticalScrollBar()
                old_scroll_value = scroll_bar.value()
                
                cursor_pos = scroll_area.viewport().mapFromGlobal(QCursor.pos())
                cursor_y = cursor_pos.y()
                
                doc_y_before = old_scroll_value + cursor_y
                old_zoom = self.zoom_vm.get_zoom()
                
                delta = wheel_event.angleDelta().y()
                zoom_change = (delta / 120.0) * 10
                
                new_zoom = old_zoom + zoom_change
                new_zoom = max(ZoomViewModel.MIN_ZOOM, min(ZoomViewModel.MAX_ZOOM, new_zoom))
                new_zoom = int(new_zoom)
                
                self.zoom_vm.set_zoom(new_zoom)
                
                if old_zoom > 0:
                    zoom_ratio = new_zoom / old_zoom
                    new_scroll_value = int(doc_y_before * zoom_ratio - cursor_y)
                    
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(10, lambda: scroll_bar.setValue(new_scroll_value))
                
                return True
        
        return super().eventFilter(obj, event)

    def load_file(self, file_path: str):
        """Public API for loading documents."""
        self.vm.load_document(file_path)

    def _handle_page_request(self, page_index: int, zoom_level: int):
        """Bridge to launch async page render at specified zoom level."""
        asyncio.create_task(self.vm.request_page(page_index, zoom_level))

    def _handle_zoom_committed(self, zoom_level: int):
        """Called after zoom debounce - update ViewModel and trigger re-render."""
        self.vm.set_zoom(zoom_level)
        self.viewer.handle_zoom_committed(zoom_level)