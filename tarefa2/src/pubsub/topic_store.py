"""Instance-local publication history, independent of routing and simulation."""
from copy import deepcopy

from src.pubsub.models import Publication


class TopicStore:
    """Keep the first publication for each message ID in arrival order.

    IDs are unique across topics within this store, not across store instances.
    History is in insertion order; created_at is preserved and never used to
    reorder arrivals. Payload copies prevent callers from mutating stored data.
    """

    def __init__(self) -> None:
        self._histories: dict[str, list[Publication]] = {}
        self._message_ids: set[str] = set()

    def add_publication(self, publication: Publication) -> bool:
        """Return True when added, False for an already known message_id.

        A duplicate never overwrites, moves or merges the original publication,
        including when the duplicate supplies a different topic or payload.
        """
        if publication.message_id in self._message_ids:
            return False
        stored = deepcopy(publication)
        self._histories.setdefault(stored.topic, []).append(stored)
        self._message_ids.add(stored.message_id)
        return True

    def get_history(self, topic: str) -> tuple[Publication, ...]:
        """Return a detached snapshot in arrival order, or () for an empty topic."""
        return tuple(deepcopy(self._histories.get(topic, ())))
