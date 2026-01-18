# client/ui/audio_visualizer.py
"""
오디오 시각화 위젯 - Equalizer 스타일
실제 오디오 파일의 스펙트럼을 분석하여 표시
"""

import os
import wave
import json
import time
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

# MP3 파일 지원을 위한 pydub (선택적)
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("[INFO] pydub not available, MP3 files will use fallback visualization")

# #region agent log helper (disabled in production)
def write_log(hypothesis_id, location, message, data=None):
    # Debug logging disabled - remove hardcoded paths for production
    pass
# #endregion

class AudioVisualizer(QWidget):
    """
    오디오 시각화 위젯 - Equalizer 바 형태
    재생 중일 때 동적으로 바의 높이가 변경됨
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)  # 최소 높이만 설정
        self.setMinimumWidth(200)  # 최소 너비 설정
        # 고정 높이 제거 - 컨테이너 크기에 맞춰 확장되도록
        # #region agent log
        write_log("A", "audio_visualizer.py:27", "__init__ size policy", {
            "min_width": self.minimumWidth(),
            "min_height": self.minimumHeight()
        })
        # #endregion
        
        # 바의 개수
        self.bar_count = 32
        
        # 각 바의 높이 (0.0 ~ 1.0)
        self.bar_heights = [0.0] * self.bar_count
        
        # 애니메이션 타이머
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.setInterval(50)  # 50ms마다 업데이트 (20 FPS)
        
        # 재생 상태
        self.is_playing = False
        
        # 오디오 데이터 및 스펙트럼
        self.audio_data = None
        self.sample_rate = None
        self.spectrum_data = None  # 시간별 스펙트럼 데이터
        self.current_time = 0.0  # 현재 재생 시간 (초)
        self.audio_duration = 0.0
        
        # 바의 너비와 간격 계산
        self.bar_width = 0
        self.bar_spacing = 0
        
    def load_audio_file(self, audio_file_path):
        """오디오 파일 로드 및 스펙트럼 분석"""
        # #region agent log
        write_log("B", "audio_visualizer.py:82", "load_audio_file entry", {
            "audio_file_path": audio_file_path,
            "file_exists": os.path.exists(audio_file_path) if audio_file_path else False,
            "file_ext": os.path.splitext(audio_file_path)[1] if audio_file_path else None
        })
        # #endregion
        try:
            if not os.path.exists(audio_file_path):
                print(f"[WARNING] Audio file not found: {audio_file_path}")
                # #region agent log
                write_log("B", "audio_visualizer.py:91", "load_audio_file file not found", {})
                # #endregion
                return False
            
            file_ext = os.path.splitext(audio_file_path)[1].lower()
            
            # MP3 파일인 경우 pydub 사용
            if file_ext == '.mp3':
                if not PYDUB_AVAILABLE:
                    print(f"[WARNING] pydub not available, cannot analyze MP3 file")
                    # #region agent log
                    write_log("B", "audio_visualizer.py:100", "load_audio_file pydub not available", {})
                    # #endregion
                    return False
                
                # MP3 파일 로드
                audio_segment = AudioSegment.from_mp3(audio_file_path)
                # 모노로 변환
                audio_segment = audio_segment.set_channels(1)
                # 샘플레이트 가져오기
                self.sample_rate = audio_segment.frame_rate
                # numpy 배열로 변환
                samples = audio_segment.get_array_of_samples()
                audio_int16 = np.array(samples, dtype=np.int16)
                # float32로 정규화 (-1.0 ~ 1.0)
                self.audio_data = audio_int16.astype(np.float32) / 32768.0
                self.audio_duration = len(self.audio_data) / self.sample_rate
                
                # 스펙트럼 분석
                self._analyze_spectrum()
                # #region agent log
                write_log("B", "audio_visualizer.py:120", "load_audio_file MP3 success", {
                    "audio_duration": self.audio_duration,
                    "spectrum_data_len": len(self.spectrum_data) if self.spectrum_data is not None else 0
                })
                # #endregion
                return True
            
            # WAV 파일 읽기
            with wave.open(audio_file_path, 'rb') as wav_file:
                self.sample_rate = wav_file.getframerate()
                n_channels = wav_file.getnchannels()
                n_frames = wav_file.getnframes()
                sample_width = wav_file.getsampwidth()
                
                # 오디오 데이터 읽기
                frames = wav_file.readframes(n_frames)
                
                # int16로 변환
                if sample_width == 2:
                    audio_int16 = np.frombuffer(frames, dtype=np.int16)
                else:
                    print(f"[WARNING] Unsupported sample width: {sample_width}")
                    return False
                
                # 모노로 변환 (스테레오인 경우 평균)
                if n_channels == 2:
                    audio_int16 = audio_int16.reshape(-1, 2).mean(axis=1).astype(np.int16)
                
                # float32로 정규화 (-1.0 ~ 1.0)
                self.audio_data = audio_int16.astype(np.float32) / 32768.0
                self.audio_duration = len(self.audio_data) / self.sample_rate
                
                # 스펙트럼 분석 (시간별로 분할)
                self._analyze_spectrum()
                # #region agent log
                write_log("B", "audio_visualizer.py:100", "load_audio_file success", {
                    "audio_duration": self.audio_duration,
                    "spectrum_data_len": len(self.spectrum_data) if self.spectrum_data is not None else 0,
                    "spectrum_data_shape": self.spectrum_data.shape if self.spectrum_data is not None else None
                })
                # #endregion
                return True
        except Exception as e:
            print(f"[ERROR] Failed to load audio file: {e}")
            # #region agent log
            write_log("B", "audio_visualizer.py:108", "load_audio_file exception", {"error": str(e)})
            # #endregion
            return False
    
    def _analyze_spectrum(self):
        """오디오 데이터를 시간별로 분할하여 스펙트럼 분석"""
        if self.audio_data is None or self.sample_rate is None:
            return
        
        # FFT 윈도우 크기
        fft_size = 2048
        hop_size = int(self.sample_rate * 0.05)  # 50ms마다 분석
        
        # 시간별 스펙트럼 저장
        spectrum_list = []
        
        for i in range(0, len(self.audio_data) - fft_size, hop_size):
            # 오디오 블록 추출
            block = self.audio_data[i:i + fft_size]
            
            # 윈도우 함수 적용 (Hann window)
            window = np.hanning(len(block))
            windowed = block * window
            
            # FFT 수행
            fft = np.fft.rfft(windowed)
            magnitude = np.abs(fft)
            
            # 주파수 대역을 bar_count개로 그룹화
            # 0Hz ~ Nyquist frequency (sample_rate/2)를 bar_count개로 분할
            nyquist = self.sample_rate / 2
            freq_bins = np.linspace(0, nyquist, len(magnitude))
            
            # bar_count개 주파수 대역으로 그룹화
            bar_levels = np.zeros(self.bar_count)
            for bar_idx in range(self.bar_count):
                # 각 바에 해당하는 주파수 범위
                freq_start = (bar_idx / self.bar_count) * nyquist
                freq_end = ((bar_idx + 1) / self.bar_count) * nyquist
                
                # 해당 주파수 범위의 magnitude 평균
                mask = (freq_bins >= freq_start) & (freq_bins < freq_end)
                if np.any(mask):
                    bar_levels[bar_idx] = np.mean(magnitude[mask])
            
            # 정규화 (0.0 ~ 1.0)
            max_val = np.max(bar_levels)
            if max_val > 0:
                bar_levels = bar_levels / max_val
            
            spectrum_list.append(bar_levels)
        
        self.spectrum_data = np.array(spectrum_list)
        print(f"[INFO] Spectrum analysis complete: {len(spectrum_list)} time frames")
    
    def set_current_time(self, time_seconds):
        """현재 재생 시간 설정 (스펙트럼 업데이트용)"""
        # #region agent log
        write_log("C", "audio_visualizer.py:140", "set_current_time", {
            "time_seconds": time_seconds,
            "audio_duration": self.audio_duration,
            "spectrum_data_len": len(self.spectrum_data) if self.spectrum_data is not None else 0
        })
        # #endregion
        self.current_time = time_seconds
    
    def start_visualization(self):
        """시각화 시작"""
        # #region agent log
        write_log("C", "audio_visualizer.py:150", "start_visualization entry", {
            "is_playing_before": self.is_playing,
            "timer_active_before": self.animation_timer.isActive(),
            "spectrum_data_exists": self.spectrum_data is not None,
            "spectrum_data_len": len(self.spectrum_data) if self.spectrum_data is not None else 0,
            "widget_visible": self.isVisible(),
            "widget_size": (self.width(), self.height())
        })
        # #endregion
        self.is_playing = True
        self.current_time = 0.0
        if not self.animation_timer.isActive():
            self.animation_timer.start()
        # #region agent log
        write_log("C", "audio_visualizer.py:162", "start_visualization exit", {
            "is_playing_after": self.is_playing,
            "timer_active_after": self.animation_timer.isActive()
        })
        # #endregion
    
    def stop_visualization(self):
        """시각화 중지"""
        self.is_playing = False
        self.animation_timer.stop()
        # 모든 바를 0으로 리셋
        self.bar_heights = [0.0] * self.bar_count
        self.update()
    
    def update_animation(self):
        """애니메이션 업데이트 - 바 높이 변경"""
        # #region agent log
        write_log("C", "audio_visualizer.py:170", "update_animation entry", {
            "is_playing": self.is_playing,
            "spectrum_data_exists": self.spectrum_data is not None,
            "spectrum_data_len": len(self.spectrum_data) if self.spectrum_data is not None else 0,
            "current_time": self.current_time,
            "audio_duration": self.audio_duration,
            "widget_visible": self.isVisible(),
            "widget_size": (self.width(), self.height()),
            "bar_heights_sum": sum(self.bar_heights)
        })
        # #endregion
        if not self.is_playing:
            return
        
        # 실제 오디오 스펙트럼 데이터가 있으면 사용
        if self.spectrum_data is not None and len(self.spectrum_data) > 0:
            # 현재 시간에 해당하는 스펙트럼 인덱스 계산
            time_index = int((self.current_time / self.audio_duration) * len(self.spectrum_data))
            time_index = max(0, min(time_index, len(self.spectrum_data) - 1))
            
            # 해당 시간의 스펙트럼 데이터 가져오기
            target_levels = self.spectrum_data[time_index]
            
            # 부드러운 보간 (damping) - 자연스러운 애니메이션
            for i in range(self.bar_count):
                current = self.bar_heights[i]
                target = float(target_levels[i])
                # 부드러운 전환 (70% 현재값 + 30% 목표값)
                self.bar_heights[i] = current * 0.7 + target * 0.3
            
            # 재생 시간 업데이트 (타이머 간격만큼 증가)
            self.current_time += 0.05  # 50ms = 0.05초
            if self.current_time >= self.audio_duration:
                self.current_time = 0.0  # 루프
            # #region agent log
            write_log("C", "audio_visualizer.py:195", "update_animation using spectrum", {
                "time_index": int((self.current_time / self.audio_duration) * len(self.spectrum_data)) if self.audio_duration > 0 else 0,
                "bar_heights_max": max(self.bar_heights) if self.bar_heights else 0,
                "bar_heights_sum": sum(self.bar_heights)
            })
            # #endregion
        else:
            # 스펙트럼 데이터가 없으면 랜덤 시뮬레이션 (fallback)
            for i in range(self.bar_count):
                current = self.bar_heights[i]
                center_factor = 1.0 - abs(i - self.bar_count / 2) / (self.bar_count / 2)
                target = np.random.uniform(0.3, 0.9) * (0.5 + center_factor * 0.5)
                self.bar_heights[i] = current * 0.7 + target * 0.3
            # #region agent log
            write_log("C", "audio_visualizer.py:205", "update_animation using fallback", {
                "bar_heights_max": max(self.bar_heights) if self.bar_heights else 0
            })
            # #endregion
        
        self.update()
    
    def set_audio_levels(self, levels):
        """
        실제 오디오 레벨 데이터를 설정 (선택적)
        levels: [0.0 ~ 1.0] 범위의 리스트
        """
        if levels and len(levels) == self.bar_count:
            self.bar_heights = levels.copy()
            self.update()
    
    def paintEvent(self, event):
        """페인트 이벤트 - 바 그리기"""
        # #region agent log
        write_log("D", "audio_visualizer.py:213", "paintEvent entry", {
            "widget_visible": self.isVisible(),
            "widget_size": (self.width(), self.height()),
            "rect_size": (self.rect().width(), self.rect().height()),
            "bar_heights_max": max(self.bar_heights) if self.bar_heights else 0,
            "bar_heights_sum": sum(self.bar_heights)
        })
        # #endregion
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # 배경 - 검정
        painter.fillRect(rect, QColor(0, 0, 0))
        
        # 바의 너비와 간격 계산
        total_spacing = (self.bar_count - 1) * 2  # 바 사이 간격 총합
        available_width = width - 20  # 좌우 여백 10px씩
        self.bar_width = max(2, (available_width - total_spacing) // self.bar_count)
        self.bar_spacing = 2
        
        # 각 바 그리기
        start_x = 10 + (available_width - (self.bar_count * self.bar_width + (self.bar_count - 1) * self.bar_spacing)) // 2
        
        for i in range(self.bar_count):
            bar_height = int(self.bar_heights[i] * (height - 20))  # 상하 여백 10px씩
            bar_height = max(2, bar_height)  # 최소 높이 2px
            
            x = start_x + i * (self.bar_width + self.bar_spacing)
            y = height - 10 - bar_height  # 하단에서 시작
            
            # 바의 색상 - Pip-Boy 테마에 맞춤: 어두운 녹색 -> 밝은 녹색 (전체 녹색 계열)
            center_factor = 1.0 - abs(i - self.bar_count / 2) / (self.bar_count / 2)
            
            # Pip-Boy 색상 팔레트: 전체 녹색 계열
            # 어두운 녹색 (0, 100, 0) -> 주 녹색 (0, 255, 65) -> 밝은 녹색 (0, 255, 100)
            r = 0
            g = int(100 + center_factor * 155)  # 100 ~ 255
            b = int(center_factor * 100)  # 0 ~ 100 (중앙이 더 밝게)
            
            # 높이에 따른 밝기 조절
            brightness = 0.6 + self.bar_heights[i] * 0.4  # 0.6 ~ 1.0
            r = int(r * brightness)
            g = int(g * brightness)
            b = int(b * brightness)
            
            # 최소 밝기 보장 (너무 어두워지지 않도록)
            r = max(r, 20)
            g = max(g, 50)
            
            bar_color = QColor(r, g, b)
            
            # 바 그리기 (글로우 효과를 위한 그라데이션)
            gradient = QBrush(bar_color)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            
            # 바 본체
            painter.fillRect(x, y, self.bar_width, bar_height, bar_color)
            
            # 글로우 효과 (상단에 밝은 부분) - Pip-Boy 녹색 계열
            if bar_height > 4:
                # 글로우는 더 밝은 녹색
                glow_color = QColor(0, min(255, g + 80), min(255, b + 40))
                glow_height = min(bar_height // 3, 8)
                painter.fillRect(x, y, self.bar_width, glow_height, glow_color)
        
        super().paintEvent(event)
        # #region agent log
        write_log("D", "audio_visualizer.py:290", "paintEvent exit", {
            "bars_drawn": self.bar_count,
            "bar_width": self.bar_width,
            "start_x": start_x if 'start_x' in locals() else 0
        })
        # #endregion
