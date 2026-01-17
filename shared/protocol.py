# shared/protocol.py
from dataclasses import dataclass, asdict
import json

@dataclass
class Packet:
    category: str  # VISION, SCREEN
    event: str     # SLEEPING, GAMING
    data: dict

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str):
        d = json.loads(json_str)
        return Packet(**d)