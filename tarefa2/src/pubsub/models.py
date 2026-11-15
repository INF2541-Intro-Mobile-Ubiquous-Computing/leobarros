"""Data-only Pub/Sub contracts and JSON envelopes.

Node IDs are simulator IDs; regions are geographic origins, not routing faces.
Topics are not hard-coded here: configured topic membership belongs to the
future application layer. Payloads must be JSON-compatible when serialized.
"""
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, ClassVar


class Region(str, Enum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"
    C = "C"


class Operation(str, Enum):
    SUBSCRIBE = "SUBSCRIBE"
    PUBLISH = "PUBLISH"
    FETCH = "FETCH"
    DELIVER = "DELIVER"
    SYNC = "SYNC"
    REPLICATE = "REPLICATE"


@dataclass(frozen=True)
class Publication:
    message_id: str
    topic: str
    origin_id: int
    origin_region: Region
    created_at: float
    payload: Any

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin_region", Region(self.origin_region))


@dataclass(frozen=True)
class Subscription:
    subscriber_id: int
    topic: str
    accepted_regions: frozenset[Region]

    def __post_init__(self) -> None:
        # Copy the caller's set so filters cannot be changed by aliasing it.
        object.__setattr__(self, "accepted_regions",
                           frozenset(Region(region) for region in self.accepted_regions))


@dataclass(frozen=True)
class Envelope:
    """sender_id identifies the application sender, not a routing next hop."""

    sender_id: int
    operation: ClassVar[Operation]
    msg_type: ClassVar[str] = "pubsub"

    def to_dict(self) -> dict:
        # JSON conversion also produces detached containers for transmission.
        return json.loads(self.to_json())

    def to_json(self) -> str:
        data = asdict(self)
        data.update(msg_type=self.msg_type, operation=self.operation.value)
        return json.dumps(data, default=_json_default, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class SubscribeEnvelope(Envelope):
    subscription: Subscription
    operation: ClassVar[Operation] = Operation.SUBSCRIBE


@dataclass(frozen=True)
class PublishEnvelope(Envelope):
    publication: Publication
    operation: ClassVar[Operation] = Operation.PUBLISH


@dataclass(frozen=True)
class ReplicateEnvelope(Envelope):
    """Peer-to-peer copy; sender is the peer, publication origin is unchanged."""

    publication: Publication
    operation: ClassVar[Operation] = Operation.REPLICATE


@dataclass(frozen=True)
class FetchEnvelope(Envelope):
    subscriber_id: int
    topic: str
    operation: ClassVar[Operation] = Operation.FETCH


@dataclass(frozen=True)
class DeliverEnvelope(Envelope):
    subscriber_id: int
    publications: tuple[Publication, ...] = field(default_factory=tuple)
    is_push: bool = False  # distinguish live delivery from a FETCH snapshot
    operation: ClassVar[Operation] = Operation.DELIVER

    def __post_init__(self) -> None:
        object.__setattr__(self, "publications", tuple(self.publications))
        if type(self.is_push) is not bool:
            raise ValueError('is_push must be a boolean')


@dataclass(frozen=True)
class SyncEnvelope(Envelope):
    """Subscription delta with a Lamport version; sender ID breaks version ties."""

    subscriptions: tuple[Subscription, ...] = field(default_factory=tuple)
    version: int = 0  # zero preserves legacy data; live synchronization requires > 0
    operation: ClassVar[Operation] = Operation.SYNC

    def __post_init__(self) -> None:
        object.__setattr__(self, "subscriptions", tuple(self.subscriptions))
        if type(self.version) is not int or self.version < 0:
            raise ValueError('SYNC version must be a nonnegative integer')


def _json_default(value: Any) -> list:
    if isinstance(value, frozenset) and all(isinstance(item, Region) for item in value):
        return sorted(region.value for region in value)
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def envelope_from_dict(data: dict) -> Envelope:
    """Reconstruct a typed envelope without modifying the incoming dictionary.

    Missing, extra or invalid envelope fields raise ValueError. This is not a
    complete application validator (authorization, topic membership, etc.).
    """
    try:
        fields = dict(data)
        if fields.pop("msg_type") != Envelope.msg_type:
            raise ValueError("Expected msg_type='pubsub'")
        operation = Operation(fields.pop("operation"))
        if operation == Operation.SUBSCRIBE:
            fields["subscription"] = Subscription(**fields["subscription"])
            return SubscribeEnvelope(**fields)
        if operation == Operation.PUBLISH:
            fields["publication"] = Publication(**fields["publication"])
            return PublishEnvelope(**fields)
        if operation == Operation.REPLICATE:
            fields["publication"] = Publication(**fields["publication"])
            return ReplicateEnvelope(**fields)
        if operation == Operation.FETCH:
            return FetchEnvelope(**fields)
        if operation == Operation.DELIVER:
            fields["publications"] = tuple(Publication(**item) for item in fields["publications"])
            return DeliverEnvelope(**fields)
        fields["subscriptions"] = tuple(Subscription(**item) for item in fields["subscriptions"])
        return SyncEnvelope(**fields)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid Pub/Sub envelope: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def envelope_from_json(message: str) -> Envelope:
    data = json.loads(message, parse_constant=_reject_constant)
    if not isinstance(data, dict):
        raise ValueError("A Pub/Sub envelope must be a JSON object")
    return envelope_from_dict(data)
