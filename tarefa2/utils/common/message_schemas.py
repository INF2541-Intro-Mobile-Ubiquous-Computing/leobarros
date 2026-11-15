# ---------------------------------------------------------------------------
# Message schemas
# ---------------------------------------------------------------------------
from typing import Dict, List, Tuple, TypedDict, NotRequired

class SimpleMessage(TypedDict):
    """Basic message type used for template classes"""
    packets:       Dict[str, int]   # sensor_name → packet count
    sender_type:   int
    sender_id:     int
    sensor_id:     NotRequired[int]  # stable logical sensor identity, distinct from sender_id
    lamport:       int              # sender's Lamport time at send

