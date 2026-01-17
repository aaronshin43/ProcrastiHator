ProcrastiHator

## Project Structure
```
ProcrastiHator/
│
├── 📂 agent/                 # [멤버 1: Brain] 백엔드 에이전트 영역
│   ├── __init__.py
│   ├── main.py               # 🔥 에이전트 실행 진입점 (python agent/main.py)
│   ├── llm.py                # LLM 통신 및 판단 로직
│   ├── memory.py             # 단기 기억(Context) 관리 클래스
│   └── prompts.py            # 페르소나(악마조교, 일론머스크) 시스템 프롬프트 모음
│
├── 📂 client/                # [멤버 2 & 3] 클라이언트 앱 영역
│   ├── __init__.py
│   ├── main.py               # 🔥 클라이언트 실행 진입점 (python client/main.py)
│   ├── config.py             # 설정 관리
│   │
│   ├── 📂 services/          # [멤버 2: Core] 백그라운드 로직 (스레드)
│   │   ├── vision.py         # MediaPipe 웹캠 감지 QThread
│   │   ├── screen.py         # 윈도우 제목 추출 QThread
│   │   └── audio.py          # Push-to-Talk 마이크 제어 로직
│   │
│   └── 📂 ui/                # [멤버 3: UI] 화면 및 디자인
│       ├── main_window.py    # 메인 설정 창 UI
│       ├── floating_widget.py# 투명 배경 캐릭터 위젯 UI
│       ├── debug_window.py   # (F12) 개발자용 웹캠 확인 창
│       └── assets/           # 이미지, 아이콘 파일들 (.png, .gif)
│
├── 📂 shared/                # [공통] 데이터 규격 (복붙해서 사용 권장)
│   ├── protocol.py           # Packet 클래스, JSON 포맷 정의
│   └── constants.py          # TOPIC 이름, 이벤트 상수 정의
│
├── .env                      # API Key (LIVEKIT_URL, OPENAI_API_KEY 등)
├── .gitignore                # __pycache__, .env 제외 설정
├── requirements.txt          # 패키지 목록
└── README.md
```