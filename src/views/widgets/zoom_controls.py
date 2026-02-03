from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QComboBox
from PyQt6.QtCore import pyqtSignal, Qt

class ZoomControls(QWidget):
    """
    Zoom control widget with preset dropdown, +/- buttons, and fit modes.
    """
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    zoom_reset_clicked = pyqtSignal()
    preset_selected = pyqtSignal(int)
    fit_width_requested = pyqtSignal()  # NEW
    fit_page_requested = pyqtSignal()   # NEW
    
    # Special values for fit modes
    FIT_WIDTH_VALUE = -1
    FIT_PAGE_VALUE = -2
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._updating_combo = False
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Zoom out button
        self._btn_out = QPushButton("−")
        self._btn_out.setFixedSize(30, 30)
        self._btn_out.setToolTip("Zoom Out (Ctrl+-)")
        self._btn_out.clicked.connect(self.zoom_out_clicked.emit)
        
        # Preset dropdown
        self._combo = QComboBox()
        self._combo.setFixedWidth(120)
        
        # Add fit modes first
        self._combo.addItem("Fit Width", self.FIT_WIDTH_VALUE)
        self._combo.addItem("Fit Page", self.FIT_PAGE_VALUE)
        self._combo.insertSeparator(2)
        
        # Add preset percentages
        self._combo.addItem("25%", 25)
        self._combo.addItem("50%", 50)
        self._combo.addItem("75%", 75)
        self._combo.addItem("100%", 100)
        self._combo.addItem("125%", 125)
        self._combo.addItem("150%", 150)
        self._combo.addItem("200%", 200)
        self._combo.addItem("300%", 300)
        self._combo.addItem("400%", 400)
        
        # Set default to 100%
        index = self._combo.findData(100)
        if index >= 0:
            self._combo.setCurrentIndex(index)
        
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        
        # Zoom in button
        self._btn_in = QPushButton("+")
        self._btn_in.setFixedSize(30, 30)
        self._btn_in.setToolTip("Zoom In (Ctrl++)")
        self._btn_in.clicked.connect(self.zoom_in_clicked.emit)
        
        # Reset button
        self._btn_reset = QPushButton("⟲")
        self._btn_reset.setFixedSize(30, 30)
        self._btn_reset.setToolTip("Reset Zoom (Ctrl+0)")
        self._btn_reset.clicked.connect(self.zoom_reset_clicked.emit)
        
        layout.addWidget(self._btn_out)
        layout.addWidget(self._combo)
        layout.addWidget(self._btn_in)
        layout.addWidget(self._btn_reset)
        layout.addStretch()
    
    def _on_combo_changed(self, index):
        """Handle selection from dropdown."""
        if self._updating_combo:
            return
        
        value = self._combo.itemData(index)
        if value == self.FIT_WIDTH_VALUE:
            self.fit_width_requested.emit()
        elif value == self.FIT_PAGE_VALUE:
            self.fit_page_requested.emit()
        elif value and value > 0:
            self.preset_selected.emit(value)
    
    def update_zoom_display(self, zoom_level: int, is_fit_mode: bool = False, fit_mode_name: str = None):
        """
        Update the dropdown display.
        
        zoom_level: Current zoom percentage
        is_fit_mode: True if in fit-width or fit-page mode
        fit_mode_name: "Fit Width" or "Fit Page" if in fit mode
        """
        self._updating_combo = True
        
        if is_fit_mode and fit_mode_name:
            # Select the fit mode in dropdown
            if fit_mode_name == "Fit Width":
                index = self._combo.findData(self.FIT_WIDTH_VALUE)
            elif fit_mode_name == "Fit Page":
                index = self._combo.findData(self.FIT_PAGE_VALUE)
            else:
                index = -1
            
            if index >= 0:
                self._combo.setCurrentIndex(index)
        else:
            # Check if this is a preset value
            index = self._combo.findData(zoom_level)
            if index >= 0:
                self._combo.setCurrentIndex(index)
            else:
                # Custom zoom level - could display as "Custom: 137%"
                # For now, just don't change selection
                pass
        
        # Update button states
        from ...viewmodels.zoom_viewmodel import ZoomViewModel
        self._btn_out.setEnabled(zoom_level > ZoomViewModel.MIN_ZOOM)
        self._btn_in.setEnabled(zoom_level < ZoomViewModel.MAX_ZOOM)
        
        self._updating_combo = False