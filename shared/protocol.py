from dataclasses import dataclass, field, asdict
import time
import json
from typing import Any, Dict

@dataclass
class PacketMeta:
    category: str  # VISION, SCREEN, SYSTEM
    timestamp: float = field(default_factory=time.time)

@dataclass
class Packet:
    event: str     # DROWSY, WINDOW_CHANGE...
    data: Dict[str, Any]
    meta: PacketMeta

    # 전송용: 객체 -> JSON String 변환
    def to_json(self):
        return json.dumps({
            "meta": asdict(self.meta),
            "event": self.event,
            "data": self.data
        })

    # 수신용: JSON String -> 객체 변환
    @staticmethod
    def from_json(json_str):
        d = json.loads(json_str)
        return Packet(
            event=d['event'],
            data=d['data'],
            meta=PacketMeta(**d['meta'])
        )