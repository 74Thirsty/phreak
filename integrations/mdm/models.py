from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class Device:
    id: int
    imei: str
    model: str
    phone_number: Optional[str] = None
    policy_id: Optional[int] = None
    last_seen: Optional[str] = None

@dataclass
class Policy:
    id: int
    name: str
    apps: List[str]
    restrictions: Dict[str, object] = field(default_factory=dict)
