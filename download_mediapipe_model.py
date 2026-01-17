"""
MediaPipe Face Landmarker 모델 다운로드 스크립트
"""
import os
import urllib.request

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_PATH = os.path.join("client", "services", "face_landmarker.task")

def download_model():
    """Face Landmarker 모델 다운로드"""
    print(f"다운로드 중: {MODEL_URL}")
    print(f"저장 위치: {MODEL_PATH}")
    
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"[OK] 모델 다운로드 완료: {MODEL_PATH}")
        print(f"파일 크기: {os.path.getsize(MODEL_PATH) / (1024*1024):.2f} MB")
    except Exception as e:
        print(f"[ERROR] 다운로드 실패: {e}")
        return False
    
    return True

if __name__ == "__main__":
    download_model()
