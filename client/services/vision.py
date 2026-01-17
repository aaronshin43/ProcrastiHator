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

# shared 폴더 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.protocol import Packet, PacketMeta
from shared.constants import VisionEvents, PacketCategory

class VisionWorker(QThread):
    # 메인 UI로 보낼 신호 정의
    alert_signal = pyqtSignal(object) # Packet 객체를 보냄

    def __init__(self, show_debug_window=False):
        super().__init__()
        self.running = False
        self.show_debug_window = show_debug_window  # 디버그 창 표시 여부
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
        
        # 상태 추적 (카운터 방식)
        self.eye_closed_counter = 0  # 눈 감음 연속 프레임 카운터
        self.no_face_counter = 0  # 얼굴 부재 연속 프레임 카운터
        self.last_alert_time = {}  # 각 이벤트별 마지막 알림 시간 (중복 방지)
        
        # EAR 임계값
        self.EAR_THRESHOLD = 0.25  # 눈 감음 임계값
        self.EAR_CONSECUTIVE_FRAMES = 100  # 연속 프레임 수 (졸음 감지 임계값)
        self.NO_FACE_CONSECUTIVE_FRAMES = 100  # 얼굴 부재 연속 프레임 수
        
        # 눈 랜드마크 인덱스 (EAR 계산용)
        self.LEFT_EYE_EAR = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE_EAR = [362, 385, 387, 263, 390, 374]
        
        # 얼굴 방향 계산용 랜드마크
        self.NOSE_TIP = 1
        self.CHIN = 175
        self.LEFT_EYE_CENTER = 33
        self.RIGHT_EYE_CENTER = 362
    
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
    
    def calculate_face_orientation(self, landmarks, frame_width, frame_height):
        """얼굴 방향 계산 (pitch, yaw)"""
        # 3D 랜드마크에서 얼굴 방향 추정
        nose_tip = landmarks[self.NOSE_TIP]
        chin = landmarks[self.CHIN]
        left_eye = landmarks[self.LEFT_EYE_CENTER]
        right_eye = landmarks[self.RIGHT_EYE_CENTER]
        
        # 눈 중심점
        eye_center_x = (left_eye.x + right_eye.x) / 2
        eye_center_y = (left_eye.y + right_eye.y) / 2
        
        # 얼굴 중심점
        face_center_x = (eye_center_x + chin.x) / 2
        face_center_y = (eye_center_y + chin.y) / 2
        
        # 프레임 중심과의 차이 계산
        frame_center_x = 0.5
        frame_center_y = 0.5
        
        # Yaw (좌우 회전)
        yaw = (face_center_x - frame_center_x) * 2  # -1 ~ 1 범위
        
        # Pitch (상하 회전)
        pitch = (face_center_y - frame_center_y) * 2  # -1 ~ 1 범위
        
        return pitch, yaw
    
    def draw_debug_info(self, frame, face_landmarks, avg_ear, pitch, yaw, is_sleeping, is_absent):
        """디버그 정보를 프레임에 그리기"""
        frame_height, frame_width = frame.shape[:2]
        
        # 상태 정보 텍스트
        y_offset = 30
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        
        # 얼굴 감지 여부 표시
        if face_landmarks:
            # 얼굴이 감지됨
            cv2.putText(frame, "Face: DETECTED", (10, y_offset),
                       font, font_scale, (0, 255, 0), thickness)
            
            # 눈 영역 그리기
            for eye_indices in [self.LEFT_EYE_EAR, self.RIGHT_EYE_EAR]:
                eye_points = []
                for idx in eye_indices:
                    if idx < len(face_landmarks):
                        point = face_landmarks[idx]
                        x = int(point.x * frame_width)
                        y = int(point.y * frame_height)
                        eye_points.append((x, y))
                        cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
                
                # 눈 윤곽선 그리기
                if len(eye_points) >= 4:
                    pts = np.array(eye_points, np.int32)
                    cv2.polylines(frame, [pts], True, (0, 255, 0), 1)
            
            y_offset += 25
            
            # EAR 값
            ear_color = (0, 255, 0) if avg_ear >= self.EAR_THRESHOLD else (0, 0, 255)
            cv2.putText(frame, f"EAR: {avg_ear:.3f}", (10, y_offset), 
                       font, font_scale, ear_color, thickness)
            y_offset += 25
            
            # 얼굴 방향
            cv2.putText(frame, f"Pitch: {pitch:.2f}, Yaw: {yaw:.2f}", (10, y_offset),
                       font, font_scale, (255, 255, 255), thickness)
            y_offset += 25
            
            # 눈 감음 프레임 수
            cv2.putText(frame, f"Closed Frames: {self.eye_closed_counter}/{self.EAR_CONSECUTIVE_FRAMES}", 
                       (10, y_offset), font, font_scale, (255, 255, 255), thickness)
            y_offset += 25
        else:
            # 얼굴이 감지되지 않음
            cv2.putText(frame, "Face: NOT DETECTED", (10, y_offset),
                       font, font_scale, (0, 0, 255), thickness)
            y_offset += 25
            
            # 얼굴 부재 프레임 수
            cv2.putText(frame, f"No Face Frames: {self.no_face_counter}/{self.NO_FACE_CONSECUTIVE_FRAMES}", 
                       (10, y_offset), font, font_scale, (255, 255, 255), thickness)
            y_offset += 25
        
        # 상태 표시 (항상 표시)
        if is_sleeping:
            cv2.putText(frame, "SLEEPING!", (10, y_offset),
                       font, 0.8, (0, 0, 255), 2)
            y_offset += 30
        if is_absent:
            cv2.putText(frame, "ABSENT!", (10, y_offset),
                       font, 0.8, (255, 0, 0), 2)
            y_offset += 30
        
        return frame

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
                    pitch, yaw = 0.0, 0.0  # 얼굴 방향
                    
                    if detection_result.face_landmarks:
                        # 얼굴이 감지됨 - 얼굴 부재 카운터 리셋
                        self.no_face_counter = 0
                        face_landmarks = detection_result.face_landmarks[0]  # 첫 번째 얼굴
                        
                        # 눈 감음 감지 (EAR 계산)
                        left_ear = self.calculate_ear(face_landmarks, self.LEFT_EYE_EAR)
                        right_ear = self.calculate_ear(face_landmarks, self.RIGHT_EYE_EAR)
                        avg_ear = (left_ear + right_ear) / 2.0
                        
                        # 눈이 감겼는지 확인
                        if avg_ear < self.EAR_THRESHOLD:
                            # 눈이 감음 - 카운터 증가
                            self.eye_closed_counter += 1
                        else:
                            # 눈이 열림 - 카운터 리셋
                            self.eye_closed_counter = 0
                        
                        # 연속으로 눈을 감고 있으면 졸음 감지
                        if self.eye_closed_counter >= self.EAR_CONSECUTIVE_FRAMES:
                            is_sleeping = True
                        
                        # 얼굴 방향 계산 (시선 감지용)
                        pitch, yaw = self.calculate_face_orientation(
                            face_landmarks, frame.shape[1], frame.shape[0]
                        )
                    else:
                        # 얼굴이 감지되지 않음 - 얼굴 부재 카운터 증가
                        self.no_face_counter += 1
                        # 얼굴이 없으면 눈 감음 카운터도 리셋
                        self.eye_closed_counter = 0
                        
                        # 얼굴이 일정 시간 동안 감지되지 않으면 부재 감지
                        if self.no_face_counter >= self.NO_FACE_CONSECUTIVE_FRAMES:
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
                                data={"confidence": 0.9, "duration": self.no_face_counter},
                                meta=PacketMeta(category=PacketCategory.VISION)
                            )
                            self.alert_signal.emit(packet)
                    
                    # 디버그 창 표시 (얼굴이 있든 없든 항상 표시)
                    if self.show_debug_window:
                        # 얼굴 랜드마크 추출
                        face_landmarks_for_draw = None
                        if detection_result.face_landmarks:
                            face_landmarks_for_draw = detection_result.face_landmarks[0]
                        
                        debug_frame = self.draw_debug_info(
                            frame.copy(), 
                            face_landmarks_for_draw,
                            avg_ear, pitch, yaw, is_sleeping, is_absent
                        )
                        cv2.imshow('Vision Debug', debug_frame)
                        # 'q' 키를 누르면 종료
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            self.running = False
                    
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
            if self.show_debug_window:
                cv2.destroyAllWindows()
            print("[OK] Vision Worker 종료")
    
    def stop(self):
        """스레드 종료"""
        self.running = False