# agent/main.py
import asyncio
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.plugins import openai, elevenlabs
import sys, os

# shared 폴더 import를 위한 경로 추가 (해커톤용 꼼수)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.protocol import Packet

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    print("🤖 에이전트가 방에 입장했습니다.")

    @ctx.room.on("data_received")
    def on_data(data, participant, **kwargs):
        try:
            packet = Packet.from_json(data.decode('utf-8'))
            if packet.event == "SLEEPING":
                print(f"😡 감지됨: {packet.data}")
                # TODO: 여기에 LLM 호출 및 ElevenLabs TTS 로직 추가
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))