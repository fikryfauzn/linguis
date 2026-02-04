from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QGraphicsDropShadowEffect, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor

class TranslationPopup(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        # SHADOW FIX 1: Enable transparency so the shadow can be seen
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._current_data = None
        self._is_expanded = False

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        # SHADOW FIX 2: Add padding to the window so the shadow isn't clipped
        self._layout.setContentsMargins(12, 12, 12, 12)
        
        self._container = QFrame()
        self._container.setObjectName("popupContainer")
        self._layout.addWidget(self._container)
        
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        # 1. Header Section - COMPACT
        self._header_frame = QFrame()
        self._header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(self._header_frame)
        header_layout.setContentsMargins(20, 16, 20, 12)
        header_layout.setSpacing(4)

        self._word_label = QLabel()
        self._word_label.setObjectName("wordTitle")
        
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        
        self._phonetic_label = QLabel()
        self._phonetic_label.setObjectName("pronunciation")
        
        self._pos_summary_label = QLabel()
        self._pos_summary_label.setObjectName("partOfSpeech")
        
        meta_layout.addWidget(self._phonetic_label)
        meta_layout.addWidget(self._pos_summary_label)
        meta_layout.addStretch()

        header_layout.addWidget(self._word_label)
        header_layout.addLayout(meta_layout)

        # 2. Separator
        self._line = QFrame()
        self._line.setFrameShape(QFrame.Shape.HLine)
        self._line.setObjectName("separator")

        # 3. Content Area - COMPACT
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setObjectName("scrollArea")
        
        self._content_widget = QWidget()
        self._content_widget.setObjectName("contentWidget")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(20, 16, 20, 16)
        self._content_layout.setSpacing(12)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll_area.setWidget(self._content_widget)

        self._loading_label = QLabel("Looking up...")
        self._loading_label.setObjectName("loadingLabel")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.hide()

        self._container_layout.addWidget(self._header_frame)
        self._container_layout.addWidget(self._line)
        self._container_layout.addWidget(self._scroll_area)
        self._container_layout.addWidget(self._loading_label)

    def _apply_styling(self):
        self.setStyleSheet("""
            QFrame#popupContainer {
                background-color: #FFFFFF;
                border: 1px solid #d4cfc4;
                border-radius: 4px;
            }
            QFrame#headerFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #e8e3db;
            }
            QLabel#wordTitle {
                font-family: 'Times New Roman', serif;
                font-size: 32px;
                font-weight: 800;
                color: #2a2520;
            }
            QLabel#pronunciation {
                font-family: sans-serif;
                font-size: 13px;
                color: #7a7066;
                font-style: italic;
            }
            QLabel#partOfSpeech {
                font-family: sans-serif;
                font-size: 11px;
                color: #8b7f6f;
                font-weight: bold;
                font-style: italic;
                background-color: #f5f2ed;
                padding: 2px 6px;
                border-radius: 3px;
            }
            QFrame#separator {
                color: #e8e3db;
                background-color: #e8e3db;
                max-height: 1px;
            }
            QWidget#contentWidget {
                background-color: #FFFFFF;
            }
            QScrollArea {
                border: none;
                background-color: #FFFFFF;
            }
            QLabel.defNumber {
                font-family: 'Times New Roman', serif;
                font-size: 16px;
                font-weight: bold;
                color: #6b5f51;
            }
            QLabel.defPos {
                font-family: sans-serif;
                font-size: 11px;
                color: #8b7f6f;
                font-weight: bold;
                font-style: italic;
                background-color: #f5f2ed;
                padding: 1px 4px;
                border-radius: 3px;
            }
            QLabel.defText {
                font-family: sans-serif;
                font-size: 13px;
                line-height: 1.5;
                color: #3a342e;
            }
            QPushButton#expandBtn {
                background-color: #faf8f5;
                border: 1px solid #e0dbd0;
                border-radius: 2px;
                color: #5a5248;
                font-size: 12px;
                padding: 10px;
                text-align: center;
            }
            QPushButton#expandBtn:hover {
                background-color: #f2ede5;
                border-color: #d0c9bb;
                color: #3a342e;
            }
            QLabel#loadingLabel {
                padding: 20px;
                color: #888888;
                font-style: italic;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 40))
        self._container.setGraphicsEffect(shadow)

    def show_loading(self, term: str):
        self._word_label.setText(term)
        self._phonetic_label.setText("")
        self._pos_summary_label.hide()
        
        self._clear_content()
        self._scroll_area.hide()
        self._loading_label.show()
        
        # SHADOW FIX 3: Width must account for margins (400 + 12 + 12 = 424)
        self.resize(424, 164)
        self.show()

    def show_result(self, data: dict):
        self._current_data = data
        self._is_expanded = False
        
        self._loading_label.hide()
        self._scroll_area.show()

        self._word_label.setText(data.get("word", ""))
        self._phonetic_label.setText(data.get("phonetic", ""))
        
        unique_pos = sorted(list(set(d.get("pos", "") for d in data.get("definitions", []))))
        self._pos_summary_label.setText(", ".join(unique_pos))
        self._pos_summary_label.show()

        self._render_definitions()

        self.activateWindow()
        self.raise_()
        self.setFocus()

    def _render_definitions(self):
        self._clear_content()
        
        defs = self._current_data.get("definitions", [])
        display_count = len(defs) if self._is_expanded else min(3, len(defs))
        
        for i in range(display_count):
            d = defs[i]
            self._add_definition_row(i + 1, d.get("pos", ""), d.get("text", ""))

        if not self._is_expanded and len(defs) > 3:
            remaining = len(defs) - 3
            btn = QPushButton(f"Show {remaining} more definitions")
            btn.setObjectName("expandBtn")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(self._toggle_expand)
            self._content_layout.addWidget(btn)

        QApplication.processEvents()
        self._content_widget.adjustSize()
        self._header_frame.adjustSize()

        content_height = self._content_widget.sizeHint().height()
        header_height = self._header_frame.sizeHint().height()
        
        # SHADOW FIX 4: Add margins (24px) to height calculation
        total_height = header_height + content_height + 10 + 24
        
        # Width: 400 + 24 = 424
        self.resize(424, min(524, total_height))

    def _add_definition_row(self, index: int, pos: str, text: str):
        row_widget = QWidget()
        row = QVBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 8)
        row.setSpacing(2)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        
        num_label = QLabel(self._to_roman(index) + ".")
        num_label.setProperty("class", "defNumber")
        
        pos_label = QLabel(pos)
        pos_label.setProperty("class", "defPos")
        
        meta_row.addWidget(num_label)
        meta_row.addWidget(pos_label)
        meta_row.addStretch()
        
        text_label = QLabel(text)
        text_label.setProperty("class", "defText")
        text_label.setWordWrap(True)
        
        row.addLayout(meta_row)
        row.addWidget(text_label)
        
        self._content_layout.addWidget(row_widget)

    def _toggle_expand(self):
        self._is_expanded = True
        self._render_definitions()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _to_roman(self, n: int) -> str:
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
        roman_num = ''
        i = 0
        while n > 0:
            for _ in range(n // val[i]):
                roman_num += syb[i]
                n -= val[i]
            i += 1
        return roman_num

    def closeEvent(self, event):
        self.dismissed.emit()
        super().closeEvent(event)