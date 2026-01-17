# client/services/vision.py
import sys
import os
from PyQt6.QtCore import QThread, pyqtSignal
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import Image as MPImage
from mediapipe.tasks.python.vision.core.image import ImageFormat
import numpy as np
import time
from collections import deque

# shared 폴더 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.protocol import Packet, PacketMeta
from shared.constants import VisionEvents, PacketCategory

class VisionWorker(QThread):
    # 메인 UI로 보낼 신호 정의
    alert_signal = pyqtSignal(object) # Packet 객체를 보냄

    def __init__(self):
        super().__init__()
        self.running = False
        # MediaPipe Face Landmarker 초기화 (0.10.x API)
        # 모델 파일 경로
        model_path = os.path.join(os.path.dirname(__file__), 'face_landmarker.task')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"모델 파일을 찾을 수 없습니다: {model_path}\n"
                f"다음 명령으로 모델을 다운로드하세요: python download_mediapipe_model.py"
            )
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=vision.RunningMode.IMAGE  # 이미지 모드
        )
        
        try:
            self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
        except Exception as e:
            print(f"⚠️ FaceLandmarker 초기화 실패: {e}")
            print("💡 모델 파일을 다운로드하거나 다른 방법을 시도해주세요.")
            raise
        
        # 상태 추적
        self.eye_closed_frames = deque(maxlen=20)  # 최근 20프레임 추적 (약 2초)
        self.no_face_frames = deque(maxlen=30)  # 최근 30프레임 추적 (약 3초)
        self.last_alert_time = {}  # 각 이벤트별 마지막 알림 시간 (중복 방지)
        
        # EAR 임계값
        self.EAR_THRESHOLD = 0.25  # 눈 감음 임계값
        self.EAR_CONSECUTIVE_FRAMES = 20  # 연속 프레임 수 (약 2초)
        
        # 눈 랜드마크 인덱스 (EAR 계산용)
        self.LEFT_EYE_EAR = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE_EAR = [362, 385, 387, 263, 390, 374]
    
    def calculate_ear(self, landmarks, eye_indices):
        """Eye Aspect Ratio (EAR) 계산"""
        # MediaPipe 0.10.x는 landmarks가 리스트 형태
        # 수직 거리 계산
        vertical_1 = np.linalg.norm(
            np.array([landmarks[eye_indices[1]].x, landmarks[eye_indices[1]].y]) -
            np.array([landmarks[eye_indices[5]].x, landmarks[eye_indices[5]].y])
        )
        vertical_2 = np.linalg.norm(
            np.array([landmarks[eye_indices[2]].x, landmarks[eye_indices[2]].y]) -
            np.array([landmarks[eye_indices[4]].x, landmarks[eye_indices[4]].y])
        )
        
        # 수평 거리 계산
        horizontal = np.linalg.norm(
            np.array([landmarks[eye_indices[0]].x, landmarks[eye_indices[0]].y]) -
            np.array([landmarks[eye_indices[3]].x, landmarks[eye_indices[3]].y])
        )
        
        # EAR 계산
        if horizontal == 0:
            return 0.0
        ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
        return ear
    
    def should_alert(self, event_type, cooldown_seconds=5):
        """중복 알림 방지 (쿨다운)"""
        current_time = time.time()
        last_time = self.last_alert_time.get(event_type, 0)
        
        if current_time - last_time < cooldown_seconds:
            return False
        
        self.last_alert_time[event_type] = current_time
        return True

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERROR] 웹캠을 열 수 없습니다. 웹캠이 연결되어 있는지 확인하세요.")
            self.running = False
            return
        
        print("[OK] 웹캠 연결 성공 - Vision Worker 시작")
        
        try:
            while self.running:
                try:
                    ret, frame = cap.read()
                    if not ret:
                        print("[WARNING] 프레임을 읽을 수 없습니다")
                        continue
                    
                    # MediaPipe Face Landmarker 처리
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = MPImage(image_format=ImageFormat.SRGB, data=frame_rgb)
                    detection_result = self.face_landmarker.detect(mp_image)
                    
                    is_sleeping = False
                    is_absent = False
                    avg_ear = 0.0  # 기본값
                    
                    if detection_result.face_landmarks:
                        # 얼굴이 감지됨
                        self.no_face_frames.append(True)
                        face_landmarks = detection_result.face_landmarks[0]  # 첫 번째 얼굴
                        
                        # 눈 감음 감지 (EAR 계산)
                        left_ear = self.calculate_ear(face_landmarks, self.LEFT_EYE_EAR)
                        right_ear = self.calculate_ear(face_landmarks, self.RIGHT_EYE_EAR)
                        avg_ear = (left_ear + right_ear) / 2.0
                        
                        # 눈이 감겼는지 확인
                        if avg_ear < self.EAR_THRESHOLD:
                            self.eye_closed_frames.append(True)
                        else:
                            self.eye_closed_frames.append(False)
                        
                        # 연속으로 눈을 감고 있으면 졸음 감지
                        if len(self.eye_closed_frames) >= self.EAR_CONSECUTIVE_FRAMES:
                            if all(self.eye_closed_frames):
                                is_sleeping = True
                    else:
                        # 얼굴이 감지되지 않음
                        self.no_face_frames.append(False)
                        self.eye_closed_frames.append(False)
                        
                        # 얼굴이 일정 시간 동안 감지되지 않으면 부재 감지
                        if len(self.no_face_frames) >= 30:  # 약 3초
                            if not any(self.no_face_frames):
                                is_absent = True
                    
                    # 졸음 감지 시 Packet 발송
                    if is_sleeping:
                        if self.should_alert(VisionEvents.SLEEPING):
                            packet = Packet(
                                event=VisionEvents.SLEEPING,
                                data={"confidence": 0.9, "ear": avg_ear},
                                meta=PacketMeta(category=PacketCategory.VISION)
                            )
                            self.alert_signal.emit(packet)
                    
                    # 얼굴 부재 감지 시 Packet 발송
                    if is_absent:
                        if self.should_alert(VisionEvents.ABSENT):
                            packet = Packet(
                                event=VisionEvents.ABSENT,
                                data={"confidence": 0.9, "duration": len(self.no_face_frames) * 0.1},
                                meta=PacketMeta(category=PacketCategory.VISION)
                            )
                            self.alert_signal.emit(packet)
                    
                    # time.sleep(0.05) # 0.1초 대기 (10 FPS)
                
                except Exception as e:
                    # 프레임 처리 중 예외 발생 시 로그 출력하고 계속 진행
                    print(f"[ERROR] 프레임 처리 중 오류 발생: {e}")
                    import traceback
                    traceback.print_exc()
                    # 예외 발생해도 루프는 계속 진행 (다음 프레임 처리)
                    continue
        
        except Exception as e:
            # 전체 루프에서 치명적 오류 발생 시
            print(f"[ERROR] Vision Worker 치명적 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 정리 작업은 항상 실행
            self.running = False
            cap.release()
            print("[OK] Vision Worker 종료")
    
    def stop(self):
        """스레드 종료"""
        self.running = False