# client/services/vision.py
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import mediapipe as mp
import time

class VisionWorker(QThread):
    # 메인 UI로 보낼 신호 정의
    alert_signal = pyqtSignal(object) # Packet 객체를 보냄

    def run(self):
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret: continue
            
            # TODO: 여기에 MediaPipe 눈 감음 감지 로직 구현
            is_sleeping = False # (가짜 로직)
            
            if is_sleeping:
                # 메인 스레드로 신호 발송
                self.alert_signal.emit({
                    "category": "VISION", 
                    "event": "SLEEPING", 
                    "data": {"confidence": 0.9}
                })
            
            time.sleep(0.5) # 0.5초 대기 (CPU 절약)