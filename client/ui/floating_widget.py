# client/ui/floating_widget.py
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

class FloatingWidget(QWidget):
    def __init__(self):
        super().__init__()
        # 배경 투명하게 설정 (핵심)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        self.char_label = QLabel()
        
        # 이미지 로드 (멤버 3이 assets 폴더에 이미지 넣어야 함)
        pixmap = QPixmap("client/ui/assets/character_normal.png")
        self.char_label.setPixmap(pixmap)
        
        layout.addWidget(self.char_label)
        self.setLayout(layout)

    def set_angry(self):
        # TODO: 화난 이미지로 변경하는 함수
        pass