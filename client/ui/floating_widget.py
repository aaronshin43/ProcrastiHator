# client/ui/floating_widget.py
import os
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QAction
from . import name

class FloatingWidget(QWidget):
    # 우클릭 메뉴 액션 시그널
    show_settings_signal = pyqtSignal()  # 캐릭터 설정
    pause_signal = pyqtSignal()  # 일시정지
    exit_signal = pyqtSignal()  # 종료
    
    # Personality 이름 -> 이미지 파일명 매핑
    PERSONALITY_IMAGE_MAP = {
        "Gordon Ramsey": "gorden.png",
        "Gigachad": "chad.png",
        "Uncle Roger": "roger.png",
        "Anime Girl": "monika.png",
        "Korean Mom": "korea_mom.png",
        "Drill Sergeant": "surgeant.png",
        "Sportscaster": "caster.png",
        "Shakespeare": "poem.png"
    }
    
    def __init__(self):
        super().__init__()
        # 배경 투명하게 설정 (핵심)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        self.char_label = QLabel()

        # angry 상태 및 자동 복귀 타이머
        self._is_angry = False
        self._angry_reset_timer = QTimer(self)
        self._angry_reset_timer.setSingleShot(True)
        self._angry_reset_timer.timeout.connect(lambda: self.set_angry(False))
        
        # 초기 이미지 로드 (기본값 또는 personality 기반)
        self.update_image_from_personality()
        
        layout.addWidget(self.char_label)
        self.setLayout(layout)
        
        # 드래그를 위한 초기 위치 변수
        self.oldPos = None
    
    def _get_assets_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), "assets")

    def _to_angry_filename(self, filename: str) -> str:
        """
        e.g. roger.png -> roger_angry.png
        If the filename doesn't look like an image, return as-is.
        """
        base, ext = os.path.splitext(filename)
        if not ext:
            return filename
        return f"{base}_angry{ext}"

    def _resolve_image_path(self, filename: str) -> str:
        assets_dir = self._get_assets_dir()
        image_path = os.path.join(assets_dir, filename)
        if os.path.exists(image_path):
            return image_path
        return os.path.join(assets_dir, "test.png")

    def update_image_from_personality(self):
        """선택된 personality에 따라 이미지를 업데이트"""
        # personality에 맞는 이미지 파일명 찾기
        personality = name.user_personality
        base_filename = self.PERSONALITY_IMAGE_MAP.get(personality, "test.png")

        # angry 상태면 angry 파일로 시도 (없으면 normal로 폴백)
        if self._is_angry:
            angry_filename = self._to_angry_filename(base_filename)
            angry_path = os.path.join(self._get_assets_dir(), angry_filename)
            if os.path.exists(angry_path):
                image_path = angry_path
            else:
                image_path = self._resolve_image_path(base_filename)
        else:
            image_path = self._resolve_image_path(base_filename)
        
        # 이미지 로드
        pixmap = QPixmap(image_path)
        
        # 크기를 1/12로 줄이기 (기존 1/10보다 작게)
        if not pixmap.isNull():
            new_width = pixmap.width() // 12
            new_height = pixmap.height() // 12
            # 0이 되면 안되므로 최소 1픽셀 보장
            new_width = max(1, new_width)
            new_height = max(1, new_height)
            
            pixmap = pixmap.scaled(
                new_width, 
                new_height, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
        
        self.char_label.setPixmap(pixmap)

    def mousePressEvent(self, event):
        """마우스 클릭 시 위치 저장 또는 우클릭 메뉴 표시"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self.mousePressRight(event)

    def mouseMoveEvent(self, event):
        """마우스 이동 시 창 이동"""
        if self.oldPos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

    def mousePressRight(self, event):
        """우클릭 시 설정 메뉴 표시"""
        menu = QMenu(self)
        
        # 캐릭터 설정 액션
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_signal.emit)
        menu.addAction(settings_action)
        
        # 일시정지 액션
        pause_action = QAction("Pause", self)
        pause_action.triggered.connect(self.pause_signal.emit)
        menu.addAction(pause_action)
        
        # 구분선
        menu.addSeparator()
        
        # 종료 액션
        exit_action = QAction("Quit", self)
        exit_action.triggered.connect(self.exit_signal.emit)
        menu.addAction(exit_action)
        
        # 메뉴를 마우스 위치에 표시
        menu.exec(event.globalPosition().toPoint())

    def set_angry(self, angry: bool = True):
        """화난(angry) 이미지로 변경/해제"""
        angry = bool(angry)
        if self._is_angry == angry:
            return
        self._is_angry = angry
        # 상태가 바뀌면 현재 personality 기준으로 즉시 리로드
        self.update_image_from_personality()

    def set_angry_for(self, seconds: float = 5.0):
        """일정 시간 동안 angry로 표시한 뒤 자동 복귀"""
        try:
            ms = max(0, int(float(seconds) * 1000))
        except Exception:
            ms = 5000

        self.set_angry(True)
        self._angry_reset_timer.start(ms)

