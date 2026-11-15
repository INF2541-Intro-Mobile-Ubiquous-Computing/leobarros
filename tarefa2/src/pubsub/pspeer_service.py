"""Local PSPeer application service, independent of simulated transport."""
from src.pubsub.consumption_store import ConsumptionStore
from src.pubsub.models import Publication, Subscription, SyncEnvelope
from src.pubsub.subscription_store import SubscriptionStore
from src.pubsub.topic_store import TopicStore


class PSPeerService:
    """Own local topic, subscription and consumption state for one peer.

    Methods accept application models directly. Subscription delta versions are
    local state; envelope dispatch and network sends remain in the adapter.
    """

    def __init__(self) -> None:
        self._topics = TopicStore()
        self._subscriptions = SubscriptionStore()
        self._consumption = ConsumptionStore(self._topics, self._subscriptions)
        self._subscription_clock = 0
        self._subscription_versions: dict[tuple[int, str], tuple[int, int]] = {}

    def subscribe_local(self, subscription: Subscription, peer_id: int) -> SyncEnvelope | None:
        """Apply a changed client filter and produce one versioned delta to send."""
        if not self.subscribe(subscription):
            return None
        self._subscription_clock += 1
        key = (subscription.subscriber_id, subscription.topic)
        self._subscription_versions[key] = (self._subscription_clock, peer_id)
        return SyncEnvelope(peer_id, (subscription,), self._subscription_clock)

    def apply_sync(self, message: SyncEnvelope) -> int:
        """Apply newer deltas without producing a new delta or clearing consumption.

        Lamport version then peer ID gives a deterministic conflict order, not
        wall-clock recency. Losses remain unrepaired without later updates.
        """
        if message.version == 0:
            return 0
        self._subscription_clock = max(self._subscription_clock, message.version)
        stamp = (message.version, message.sender_id)
        applied = 0
        for subscription in message.subscriptions:
            key = (subscription.subscriber_id, subscription.topic)
            if stamp <= self._subscription_versions.get(key, (0, -1)):
                continue
            self._subscription_versions[key] = stamp
            self.subscribe(subscription)
            applied += 1
        return applied

    def subscribe(self, subscription: Subscription) -> bool:
        """Register or replace a filter; return whether it changed.

        Existing consumption is preserved when the subscription is updated.
        """
        return self._subscriptions.add_subscription(subscription)

    def publish(self, publication: Publication) -> bool:
        """Store a publication; return False for an already known message ID."""
        return self._topics.add_publication(publication)

    def fetch(self, subscriber_id: int, topic: str) -> tuple[Publication, ...]:
        """Read eligible, unconsumed history without marking it as delivered."""
        return self._consumption.get_unread(subscriber_id, topic)

    def mark_consumed(self, subscriber_id: int, topic: str, message_id: str) -> bool:
        """Record receipt explicitly confirmed by the caller, never just a send.

        Return False for unknown subscription/ID or repeated confirmation.
        """
        return self._consumption.mark_consumed(subscriber_id, topic, message_id)
