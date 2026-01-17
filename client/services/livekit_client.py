import asyncio
import sys
import os
from typing import Optional
from livekit import rtc, api
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# shared 폴더 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.protocol import Packet
from client.config import Config


class LiveKitClient(QObject):
    """LiveKit client for sending detection packets"""
    
    # 신호 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.room: Optional[rtc.Room] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[QThread] = None
        self._connected = False
    
    def connect(self):
        """LiveKit 방에 연결 (비동기 실행을 위한 스레드 시작)"""
        if self._connected:
            return
        
        # 별도 스레드에서 asyncio 이벤트 루프 실행
        self._thread = LiveKitThread(self)
        self._thread.start()
    
    def disconnect(self):
        """연결 종료"""
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait()
        self._connected = False
    
    def send_packet(self, packet: Packet):
        """Packet을 LiveKit으로 전송"""
        if not self._connected or not self.room:
            print("Warning: LiveKit not connected, packet not sent")
            return
        
        # 비동기 함수를 스레드에서 실행
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._send_packet_async(packet),
                self._loop
            )
    
    async def _send_packet_async(self, packet: Packet):
        """비동기 패킷 전송"""
        try:
            if self.room and self.room.local_participant:
                data = packet.to_json().encode('utf-8')
                await self.room.local_participant.publish_data(
                    data,
                    topic="detection"
                )
        except Exception as e:
            print(f"Error sending packet: {e}")
            self.error_signal.emit(str(e))
    
    async def _connect_async(self):
        """비동기 연결 로직"""
        try:
            # Access Token 생성
            token = Config.get_livekit_token()
            
            # Room 생성 및 연결
            self.room = rtc.Room()
            
            # 이벤트 핸들러
            @self.room.on("connected")
            def on_connected():
                print("✅ LiveKit에 연결되었습니다")
                self._connected = True
                self.connected_signal.emit()
            
            @self.room.on("disconnected")
            def on_disconnected():
                print("❌ LiveKit 연결이 끊어졌습니다")
                self._connected = False
                self.disconnected_signal.emit()
            
            # 연결
            await self.room.connect(
                Config.LIVEKIT_URL,
                token
            )
            
            # 이벤트 루프 유지
            await asyncio.sleep(3600)  # 1시간 대기 (실제로는 무한 루프)
            
        except Exception as e:
            print(f"LiveKit 연결 오류: {e}")
            self.error_signal.emit(str(e))
            self._connected = False
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connected


class LiveKitThread(QThread):
    """LiveKit 비동기 이벤트 루프를 실행하는 스레드"""
    
    def __init__(self, client: LiveKitClient):
        super().__init__()
        self.client = client
        self._running = False
    
    def run(self):
        """스레드 실행 - asyncio 이벤트 루프 시작"""
        self._running = True
        self.client._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.client._loop)
        
        try:
            self.client._loop.run_until_complete(self.client._connect_async())
        except Exception as e:
            print(f"LiveKit thread error: {e}")
        finally:
            self.client._loop.close()
            self.client._loop = None
    
    def stop(self):
        """스레드 종료"""
        self._running = False
        if self.client._loop:
            self.client._loop.call_soon_threadsafe(self.client._loop.stop)
