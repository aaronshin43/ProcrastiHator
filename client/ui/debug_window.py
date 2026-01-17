"""
디버그 윈도우 모듈
VisionWorker로부터 받은 OpenCV 이미지를 표시합니다.
"""

import cv2
import numpy as np
from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QSizePolicy
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal

class DebugWindow(QMainWindow):
    """
    웹캠 영상을 표시하는 전용 디버그 윈도우.
    VisionWorker로부터 받은 이미지를 표시만 담당.
    """
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ProcrastiHator - Vision Debug")
        self.setGeometry(100, 100, 800, 600)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 레이아웃
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 비디오 표시용 라벨
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 기본 텍스트
        self.video_label.setText("Waiting for video stream...")
        self.video_label.setStyleSheet("background-color: #222; color: #aaa; font-size: 20px;")
        
        layout.addWidget(self.video_label)

    def update_image(self, frame_cv):
        """
        VisionWorker로부터 받은 OpenCV 이미지(numpy array)를 화면에 표시
        """
        if frame_cv is None:
            return
        
        try:
            # OpenCV 이미지를 QImage로 변환
            # OpenCV는 BGR, PyQt는 RGB 사용하므로 변환 필요
            rgb_image = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # 라벨 크기에 맞춰 스케일링
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.video_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.video_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Debug Image Update Error: {e}")

    def closeEvent(self, event):
        """창을 닫을 때 숨기기만 하고 완전히 끄지는 않음 (Main에서 관리)"""
        event.ignore()
        self.hide()

