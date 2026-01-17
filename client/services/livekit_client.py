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
from client.services.audio import AudioPlayer

class LiveKitWorker(QThread):
    def __init__(self):
        super().__init__()
        self.loop = None
        self._ready_event = asyncio.Event() # For internal sync if needed, but we use sleep in main thread

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # 루프 무한 실행
        self.loop.run_forever()

class LiveKitClient(QObject):
    """LiveKit client for sending detection packets"""
    
    # 신호 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.room: Optional[rtc.Room] = None
        self._connected = False
        self._paused = False
        self.audio_players = {} # track_sid -> AudioPlayer
        
        # 영속적인 백그라운드 워커 스레드 시작
        self._worker = LiveKitWorker()
        self._worker.start()
        
        # 루프가 준비될 때까지 잠시 대기 (간단한 동기화)
        import time
        while self._worker.loop is None:
            time.sleep(0.01)

    def connect(self):
        """LiveKit 방에 연결 요청"""
        if self._connected:
            return
        
        self._paused = False
        # 워커 스레드의 루프에 연결 태스크 제출
        asyncio.run_coroutine_threadsafe(self._connect_room(), self._worker.loop)

    def disconnect(self):
        """연결 종료 요청"""
        if self._connected:
             asyncio.run_coroutine_threadsafe(self._disconnect_room(), self._worker.loop)
    
    async def _connect_room(self):
        """실제 연결 로직 (Coroutine)"""
        if self._connected: return

        try:
            print("🔑 Generating token...")
            token = Config.get_livekit_token()
            
            self.room = rtc.Room()
            
            print(f"🔗 Connecting to Room: {Config.LIVEKIT_URL}")
            
            # 이벤트 핸들러 설정 (Connect 전)
            @self.room.on("connected")
            def on_connected():
                print("✅ Event: LiveKit에 연결되었습니다")
            
            @self.room.on("disconnected")
            def on_disconnected():
                print("❌ Event: LiveKit 연결이 끊어졌습니다")
                self._connected = False
                self.disconnected_signal.emit()

            @self.room.on("track_subscribed")
            def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    print(f"🎤 Audio Track Subscribed: {track.sid}")
                    player = AudioPlayer(self._worker.loop)
                    self.audio_players[track.sid] = player
                    # 비동기 태스크로 오디오 재생 시작
                    asyncio.run_coroutine_threadsafe(player.start(track), self._worker.loop)

            @self.room.on("track_unsubscribed")
            def on_track_unsubscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
                if track.kind == rtc.TrackKind.KIND_AUDIO:
                    print(f"🔇 Audio Track Unsubscribed: {track.sid}")
                    if track.sid in self.audio_players:
                        self.audio_players[track.sid].stop()
                        del self.audio_players[track.sid]

            await self.room.connect(Config.LIVEKIT_URL, token)
            
            print("✅ Connection established!")
            self._connected = True
            self.connected_signal.emit()
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.error_signal.emit(str(e))
            self._connected = False

    async def _disconnect_room(self):
        """실제 연결 해제 로직 (Coroutine)"""
        if not self.room: return
        try:
            print("🔻 Disconnecting from room...")
            await self.room.disconnect()
            
            # 오디오 플레이어 정리
            for sid, player in self.audio_players.items():
                player.stop()
            self.audio_players.clear()

            # 명시적 정리
            self.room = None
            self._connected = False
            print("✅ Disconnected successfully")
        except Exception as e:
            print(f"Error disconnecting: {e}")

    def quit(self):
        """애플리케이션 종료 시 호출"""
        if self._worker.loop:
            self._worker.loop.call_soon_threadsafe(self._worker.loop.stop)
        self._worker.quit()
        self._worker.wait()

    def set_paused(self, paused: bool):
        """전송 일시중지 설정"""
        self._paused = paused
        status = "Paused" if paused else "Resumed"
        print(f"⏸️ LiveKit Client is now {status}")

    def is_paused(self) -> bool:
        return self._paused

    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._connected

    def send_packet(self, packet: Packet):
        """Packet을 LiveKit으로 전송"""
        if not self._connected or not self.room or self._paused:
            return
        
        # Room 연결 상태 확인
        if self.room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
            return
        
        # 워커 루프에 패킷 전송 태스크 제출
        if self._worker.loop and self._worker.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_packet_async(packet),
                self._worker.loop
            )
    
    async def _send_packet_async(self, packet: Packet):
        """비동기 패킷 전송"""
        if not self.room or not self.room.local_participant: return
        try:
            data = packet.to_json().encode('utf-8')
            await self.room.local_participant.publish_data(
                data, topic="detection", reliable=True
            )
        except Exception as e:
            print(f"Error sending packet: {e}")
