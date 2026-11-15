"""Local PSPeer application service, independent of simulated transport."""
from src.pubsub.consumption_store import ConsumptionStore
from src.pubsub.models import Publication, Subscription
from src.pubsub.subscription_store import SubscriptionStore
from src.pubsub.topic_store import TopicStore


class PSPeerService:
    """Own local topic, subscription and consumption state for one peer.

    Methods accept application models directly. Envelope dispatch, replication
    and delivery acknowledgments over the network are not implemented here.
    """

    def __init__(self) -> None:
        self._topics = TopicStore()
        self._subscriptions = SubscriptionStore()
        self._consumption = ConsumptionStore(self._topics, self._subscriptions)

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
