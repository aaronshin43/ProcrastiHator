import os
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 로드 (프로젝트 루트에서)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Config:
    """Configuration manager for client application"""
    
    # LiveKit 설정
    LIVEKIT_URL = os.getenv('LIVEKIT_URL', '')
    LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY', '')
    LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', '')
    
    # Room 설정
    ROOM_NAME = os.getenv('LIVEKIT_ROOM_NAME', 'procrastihator-room')
    PARTICIPANT_NAME = os.getenv('LIVEKIT_PARTICIPANT_NAME', 'client')
    
    @classmethod
    def validate(cls):
        """필수 설정값 검증"""
        required = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return True
    
    @classmethod
    def get_livekit_token(cls):
        """LiveKit Access Token 생성 (간단한 버전 - 실제로는 서버에서 생성해야 함)"""
        # TODO: 실제로는 서버에서 토큰을 받아야 하지만, 
        # MVP에서는 클라이언트가 직접 생성할 수도 있음
        # livekit 패키지의 AccessToken을 사용할 수 있음
        from livekit import api
        token = api.AccessToken(cls.LIVEKIT_API_KEY, cls.LIVEKIT_API_SECRET) \
            .with_identity(cls.PARTICIPANT_NAME) \
            .with_name(cls.PARTICIPANT_NAME) \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=cls.ROOM_NAME,
                can_publish=True,
                can_subscribe=True,
            ))
        return token.to_jwt()
