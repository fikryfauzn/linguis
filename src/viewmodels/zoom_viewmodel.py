from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class ZoomViewModel(QObject):
    zoom_preview_changed = pyqtSignal(int)
    zoom_committed = pyqtSignal(int)
    
    MIN_ZOOM = 50
    MAX_ZOOM = 400
    DEFAULT_ZOOM = 100
    ZOOM_STEP = 10
    
    # Preset zoom levels
    PRESET_LEVELS = [25, 50, 75, 100, 125, 150, 200, 300, 400]
    
    # Special zoom modes (negative values indicate mode, not percentage)
    FIT_WIDTH = -1
    FIT_PAGE = -2
    
    DEBOUNCE_MS = 300
    
    def __init__(self):
        super().__init__()
        self._zoom_level = self.DEFAULT_ZOOM
        self._zoom_mode = None  # None, FIT_WIDTH, or FIT_PAGE
        
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._commit_zoom)
    
    def get_zoom(self) -> int:
        return self._zoom_level
    
    def get_mode(self):
        """Returns current zoom mode (None, FIT_WIDTH, or FIT_PAGE)."""
        return self._zoom_mode
    
    def set_zoom(self, level: int, immediate_commit: bool = False):
        """
        Set absolute zoom level.
        immediate_commit: If True, skip debounce and commit immediately
        """
        level = max(self.MIN_ZOOM, min(self.MAX_ZOOM, level))
        if level != self._zoom_level:
            self._zoom_level = level
            self._zoom_mode = None  # Clear fit mode when manually zooming
            
            self.zoom_preview_changed.emit(self._zoom_level)
            
            if immediate_commit:
                self._debounce_timer.stop()
                self._commit_zoom()
            else:
                self._debounce_timer.stop()
                self._debounce_timer.start(self.DEBOUNCE_MS)
    
    def set_fit_width(self, calculated_zoom: int):
        """Set to fit-width mode with calculated zoom."""
        self._zoom_mode = self.FIT_WIDTH
        self._zoom_level = max(self.MIN_ZOOM, min(self.MAX_ZOOM, calculated_zoom))
        self.zoom_preview_changed.emit(self._zoom_level)
        self._debounce_timer.stop()
        self._commit_zoom()
    
    def set_fit_page(self, calculated_zoom: int):
        """Set to fit-page mode with calculated zoom."""
        self._zoom_mode = self.FIT_PAGE
        self._zoom_level = max(self.MIN_ZOOM, min(self.MAX_ZOOM, calculated_zoom))
        self.zoom_preview_changed.emit(self._zoom_level)
        self._debounce_timer.stop()
        self._commit_zoom()
    
    def _commit_zoom(self):
        """Called after user stops zooming - triggers high-quality re-render."""
        self.zoom_committed.emit(self._zoom_level)
    
    def zoom_in(self):
        self.set_zoom(self._zoom_level + self.ZOOM_STEP)
    
    def zoom_out(self):
        self.set_zoom(self._zoom_level - self.ZOOM_STEP)
    
    def reset_zoom(self):
        self.set_zoom(self.DEFAULT_ZOOM, immediate_commit=True)
    
    def set_preset(self, level: int):
        """Set to a preset zoom level (commits immediately, no debounce)."""
        self.set_zoom(level, immediate_commit=True)
    
    def get_scale_factor(self) -> float:
        return self._zoom_level / 100.0