"""Local unread-history queries and explicit consumption acknowledgments."""
from src.pubsub.models import Publication
from src.pubsub.subscription_store import SubscriptionStore, matches
from src.pubsub.topic_store import TopicStore


class ConsumptionStore:
    """Track consumed IDs per subscriber/topic without changing topic history.

    The owning service supplies its local stores. No state is shared globally.
    Querying is read-only; the caller must explicitly confirm actual receipt.
    """

    def __init__(self, topics: TopicStore, subscriptions: SubscriptionStore) -> None:
        self._topics = topics
        self._subscriptions = subscriptions
        self._consumed: dict[tuple[int, str], set[str]] = {}

    def get_unread(self, subscriber_id: int, topic: str) -> tuple[Publication, ...]:
        """Return eligible unread history in arrival order, including old items."""
        subscription = self._subscriptions.get_subscription(subscriber_id, topic)
        if subscription is None:
            return ()
        consumed = self._consumed.get((subscriber_id, topic), set())
        return tuple(publication for publication in self._topics.get_history(topic)
                     if publication.message_id not in consumed
                     and matches(subscription, publication))

    def mark_consumed(self, subscriber_id: int, topic: str, message_id: str) -> bool:
        """Record confirmed receipt; return True only for a new consumption.

        Unknown subscriptions/IDs and repeated confirmations return False.
        The caller is responsible for confirming actual receipt. The current
        filter is deliberately not checked: it may have changed since delivery.
        This method neither sends ACKs nor marks an entire query as delivered.
        """
        if self._subscriptions.get_subscription(subscriber_id, topic) is None:
            return False
        key = (subscriber_id, topic)
        if message_id in self._consumed.get(key, set()):
            return False
        if not any(item.message_id == message_id for item in self._topics.get_history(topic)):
            return False
        self._consumed.setdefault(key, set()).add(message_id)
        return True
