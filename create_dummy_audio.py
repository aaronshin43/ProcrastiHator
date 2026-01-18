"""
더미 오디오 파일 생성 스크립트
간단한 톤을 생성하여 voice_example.wav 파일을 만듭니다.
"""

import os
import wave
import numpy as np

def create_dummy_audio():
    """더미 오디오 파일 생성"""
    # 오디오 파일 저장 경로
    assets_dir = os.path.join(os.path.dirname(__file__), "client", "ui", "assets")
    os.makedirs(assets_dir, exist_ok=True)
    audio_file = os.path.join(assets_dir, "voice_example.wav")
    
    # 오디오 파라미터
    sample_rate = 44100  # 44.1 kHz
    duration = 3.0  # 3초
    frequency = 440  # A4 음 (440 Hz)
    
    # 시간 배열 생성
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 사인파 생성 (부드러운 시작과 끝을 위한 envelope 적용)
    audio = np.sin(2 * np.pi * frequency * t)
    
    # Envelope 적용 (fade in/out)
    fade_samples = int(sample_rate * 0.1)  # 0.1초 fade
    envelope = np.ones(len(audio))
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    audio = audio * envelope
    
    # 볼륨 조절 (너무 크지 않게)
    audio = audio * 0.3
    
    # int16로 변환 (WAV 파일 형식)
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # WAV 파일로 저장
    with wave.open(audio_file, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16-bit (2 bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"[SUCCESS] Dummy audio file created: {audio_file}")
    print(f"   - Duration: {duration} seconds")
    print(f"   - Sample rate: {sample_rate} Hz")
    print(f"   - Frequency: {frequency} Hz")

if __name__ == "__main__":
    create_dummy_audio()
