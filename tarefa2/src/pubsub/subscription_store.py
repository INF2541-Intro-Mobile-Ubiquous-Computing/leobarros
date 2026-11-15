"""Instance-local subscriptions and regional matching; no delivery state."""
from src.pubsub.models import Publication, Subscription


def matches(subscription: Subscription, publication: Publication) -> bool:
    """A publication must match both the topic and an accepted origin region."""
    return (subscription.topic == publication.topic
            and publication.origin_region in subscription.accepted_regions)


class SubscriptionStore:
    """Keep one immutable subscription per (subscriber_id, topic)."""

    def __init__(self) -> None:
        self._subscriptions: dict[tuple[int, str], Subscription] = {}

    def add_subscription(self, subscription: Subscription) -> bool:
        """Insert or replace the filter; return False if nothing changed.

        Updating one topic does not affect the subscriber's other topics or
        another subscriber. No consumption history is managed here.
        """
        key = (subscription.subscriber_id, subscription.topic)
        if self._subscriptions.get(key) == subscription:
            return False
        self._subscriptions[key] = subscription
        return True

    def get_subscription(self, subscriber_id: int, topic: str) -> Subscription | None:
        """Return the current subscription, or None when not registered."""
        return self._subscriptions.get((subscriber_id, topic))

    def get_matching_subscriptions(self, publication: Publication) -> tuple[Subscription, ...]:
        """Return eligible subscriptions in registration order, without delivery."""
        return tuple(subscription for subscription in self._subscriptions.values()
                     if matches(subscription, publication))
