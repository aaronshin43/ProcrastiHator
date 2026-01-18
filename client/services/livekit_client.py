import asyncio
import sys
import os
from typing import Optional
from livekit import rtc, api
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# shared 폴더 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.protocol import Packet
from shared.constants import SystemEvents
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
        self._should_reconnect = False # 자동 재연결 플래그
        self._paused = False
        self.audio_players = {} # track_sid -> AudioPlayer
        self._pending_personality_packet: Optional[Packet] = None
        self._pending_session_start_packet: Optional[Packet] = None

        # 영속적인 백그라운드 워커 스레드 시작
        self._worker = LiveKitWorker()
        self._worker.start()
        
        # 루프가 준비될 때까지 잠시 대기 (간단한 동기화)
        import time
        while self._worker.loop is None:
            time.sleep(0.01)

    def connect(self):
        self._should_reconnect = True # 연결 의도 표시
        if self._connected:
            return
        
        self._paused = False
        # 워커 스레드의 루프에 연결 태스크 제출
        asyncio.run_coroutine_threadsafe(self._connect_room(), self._worker.loop)

    def disconnect(self):
        """연결 종료 요청"""
        self._should_reconnect = False # 재연결 비활성화f):
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
            def on_disconnected(*args):
                print("❌ Event: LiveKit 연결이 끊어졌습니다", args)
                self._connected = False
                self.disconnected_signal.emit()

                # 자동 재연결 시도
                if self._should_reconnect:
                    print("🔄 세션 유지 중... 3초 후 재연결을 시도합니다.")
                    asyncio.create_task(self._retry_connection())

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

            # 연결 직후 대기 중인 상태(성격 등)가 있다면 전송
            if self._pending_session_start_packet:
                print("🚀 Sending Buffered Session Start")
                await self._send_packet_async(self._pending_session_start_packet)
                self._pending_session_start_packet = None # 1회성 이벤트이므로 삭제

            if self._pending_personality_packet:
                print(f"🚀 Sending Buffered Personality: {self._pending_personality_packet.data.get('personality')}")
                await self._send_packet_async(self._pending_personality_packet)
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.error_signal.emit(str(e))
            self._connected = False
            
            # 초기 연결 실패 시에도 재시도 (선택 사항)
            if self._should_reconnect:
                print("🔄 초기 연결 실패. 3초 후 재시도합니다.")
                asyncio.create_task(self._retry_connection())

    async def _retry_connection(self):
        """재연결 대기 및 시도"""
        await asyncio.sleep(3)
        if self._should_reconnect and not self._connected:
            print("🔄 Reconnecting now...")
            await self._connect_room()

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
        # 성격 변경 패킷은 연결 여부와 상관없이 항상 최신 상태를 저장 (버퍼링)
        if packet.event == SystemEvents.PERSONALITY_UPDATE:
            print(f"📦 Buffering Personality: {packet.data.get('personality')}")
            self._pending_personality_packet = packet
        elif packet.event == SystemEvents.SESSION_START:
             print(f"📦 Buffering Session Start Event")
             self._pending_session_start_packet = packet

        """Packet을 LiveKit으로 전송"""
        if not self._connected:
            # print(f"⚠️ Packet dropped (Not Connected): {packet.event}")
            return
        
        if not self.room:
            print(f"⚠️ Packet dropped (No Room Object): {packet.event}")
            return
            
        if self._paused:
            print(f"⚠️ Packet dropped (Paused): {packet.event}")
            return
        
        # Room 연결 상태 확인
        if self.room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
            print(f"⚠️ Packet dropped (Room Status: {self.room.connection_state}): {packet.event}")
            try:
                # 상태가 CONNECTED가 아니면 재연결 시도? 아니면 그냥 로그만.
                pass 
            except:
                pass
            return
        
        # 워커 루프에 패킷 전송 태스크 제출
        if self._worker.loop and self._worker.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_packet_async(packet),
                self._worker.loop
            )
        else:
            print("⚠️ Packet dropped (Worker Loop Not Running)")
    
    async def _send_packet_async(self, packet: Packet):
        """비동기 패킷 전송"""
        if not self.room or not self.room.local_participant: 
            print("⚠️ Packet dropped (Async: No local participant)")
            return
        try:
            data = packet.to_json().encode('utf-8')
            await self.room.local_participant.publish_data(
                data, topic="detection", reliable=True
            )
            print(f"📤 Packet Sent: {packet.event}")
        except Exception as e:
            print(f"Error sending packet: {e}")
