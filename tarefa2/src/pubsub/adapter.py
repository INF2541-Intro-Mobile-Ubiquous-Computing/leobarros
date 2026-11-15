"""Core UAV requests and peer replication; no receipt ACK."""
import logging

from src.pubsub.models import (
    DeliverEnvelope, FetchEnvelope, Publication, PublishEnvelope,
    ReplicateEnvelope, SubscribeEnvelope, Subscription, SyncEnvelope,
)
from src.pubsub.subscription_store import matches
from src.pubsub.events import pubsub_event


class PubSubAdapterMixin:
    def initialize(self) -> None:
        super().initialize()
        self.selected_pspeer = None
        self._client_subscriptions = {}
        self._received_ids = {}  # per topic; retained across reconnects and peer changes

    def select_pspeer(self, node_id: int) -> None:
        """Choose one peer by simulator ID; no discovery or shared registry."""
        if type(node_id) is not int or node_id < 0:
            raise ValueError('PSPeer must be a nonnegative node ID')
        changed = self.selected_pspeer != node_id
        self.selected_pspeer = node_id
        if changed and self._client_subscriptions:
            self.resume_pubsub()

    def resume_pubsub(self) -> None:
        """Rebind known subscriptions then request only unreceived history."""
        node = self.provider.get_id()
        for topic, subscription in self._client_subscriptions.items():
            self._send_request(SubscribeEnvelope(node, subscription))
            self.fetch_pubsub(topic)

    def _send_request(self, message) -> bool:
        if self.selected_pspeer is None:
            return False
        return self.send_pubsub(self.selected_pspeer, message)

    def subscribe_pubsub(self, topic, accepted_regions) -> bool:
        node = self.provider.get_id()
        subscription = Subscription(node, topic, accepted_regions)
        self._client_subscriptions[topic] = subscription
        pubsub_event(self, 'subscription_requested', topic=topic,
                     regions=sorted(r.value for r in subscription.accepted_regions), peer=self.selected_pspeer)
        return self._send_request(SubscribeEnvelope(node, subscription))

    def publish_pubsub(self, publication: Publication) -> bool:
        node = self.provider.get_id()
        if publication.origin_id != node:
            raise ValueError('Publication origin must be this UAV')
        return self._send_request(PublishEnvelope(node, publication))

    def fetch_pubsub(self, topic: str) -> bool:
        node = self.provider.get_id()
        return self._send_request(FetchEnvelope(
            node, node, topic, tuple(sorted(self._received_ids.get(topic, set()))),
            self._client_subscriptions.get(topic)))

    def handle_pubsub(self, message, source_id: int) -> None:
        node = self.provider.get_id()
        if message.sender_id != source_id:
            return
        if isinstance(message, DeliverEnvelope):
            if source_id == self.selected_pspeer and message.subscriber_id == node:
                publications = []
                batch_ids = set()
                for publication in message.publications:
                    sub = self._client_subscriptions.get(publication.topic)
                    if (sub is not None and matches(sub, publication)
                            and publication.message_id not in self._received_ids.get(publication.topic, set())
                            and publication.message_id not in batch_ids):
                        batch_ids.add(publication.message_id)
                        publications.append(publication)
                if message.is_push and not publications:
                    return
                message = DeliverEnvelope(source_id, node, tuple(publications), message.is_push)
                logging.info('[PUBSUB client] node=%s peer=%s operation=DELIVER count=%s',
                             node, source_id, len(message.publications))
                self.on_pubsub_delivery(message)
                # Only successful application receipt enters the client ledger.
                for publication in publications:
                    self._received_ids.setdefault(publication.topic, set()).add(publication.message_id)
                    pubsub_event(self, 'publication_received', message_id=publication.message_id,
                                 topic=publication.topic, region=publication.origin_region.value,
                                 origin=publication.origin_id, created_at=publication.created_at,
                                 peer=source_id, is_push=message.is_push,
                                 regions=sorted(r.value for r in self._client_subscriptions[publication.topic].accepted_regions))
            return
        service = getattr(self, 'pspeer_service', None)
        if service is None:
            return
        if isinstance(message, SubscribeEnvelope):
            if message.subscription.subscriber_id != source_id:
                return
            delta = service.subscribe_local(message.subscription, node)
            if delta is not None:
                self.broadcast_pubsub_sync(delta)
        elif isinstance(message, SyncEnvelope):
            applied = service.apply_sync(message)
            pubsub_event(self, 'subscription_sync', source=source_id, version=message.version, applied=applied)
            logging.info('[PUBSUB sync] node=%s source=%s version=%s applied=%s',
                         node, source_id, message.version, applied)
            return
        elif isinstance(message, PublishEnvelope):
            if message.publication.origin_id != source_id:
                return
            if service.publish(message.publication):
                self._log_publication_stored(message.publication, source_id, replica=False)
                self.broadcast_pubsub_replication(ReplicateEnvelope(node, message.publication))
                self._push_publication(message.publication)
        elif isinstance(message, ReplicateEnvelope):
            inserted = service.publish(message.publication)
            logging.info('[PUBSUB replicate] node=%s source=%s message_id=%s inserted=%s',
                         node, source_id, message.publication.message_id, inserted)
            if inserted:
                self._log_publication_stored(message.publication, source_id, replica=True)
                self._push_publication(message.publication)
            return  # Never re-broadcast a received replica, even when newly stored.
        elif isinstance(message, FetchEnvelope):
            if message.subscriber_id != source_id:
                return
            if message.subscription is not None:
                # Equal-time radio events may deliver FETCH before SUBSCRIBE.
                # Apply its own filter before querying, without a separate ACK.
                delta = service.subscribe_local(message.subscription, node)
                if delta is not None:
                    self.broadcast_pubsub_sync(delta)
            service.report_received(source_id, message.topic, message.received_ids)
            publications = service.fetch(source_id, message.topic)
            pubsub_event(self, 'history_requested', subscriber=source_id, topic=message.topic,
                         reported_ids=len(message.received_ids), unread=len(publications))
            submitted = self.send_pubsub(source_id, DeliverEnvelope(node, source_id, publications))
            logging.info('[PUBSUB peer] node=%s client=%s response=DELIVER count=%s submitted=%s',
                         node, source_id, len(publications), submitted)
        else:
            return
        logging.info('[PUBSUB peer] node=%s client=%s operation=%s',
                     node, source_id, message.operation.value)

    def _log_publication_stored(self, publication: Publication, source: int, replica: bool) -> None:
        pubsub_event(self, 'publication_stored', message_id=publication.message_id,
                     topic=publication.topic, region=publication.origin_region.value,
                     origin=publication.origin_id, created_at=publication.created_at,
                     source=source, replica=replica)

    def _push_publication(self, publication: Publication) -> None:
        node = self.provider.get_id()
        for subscriber in self.pspeer_service.delivery_subscribers(publication, node):
            submitted = self.send_pubsub(
                subscriber, DeliverEnvelope(node, subscriber, (publication,), is_push=True))
            logging.info('[PUBSUB push] peer=%s subscriber=%s message_id=%s submitted=%s',
                         node, subscriber, publication.message_id, submitted)

    def on_pubsub_delivery(self, message: DeliverEnvelope) -> None:
        """Client callback for deduplicated push or FETCH results (including empty).

        Successful return records receipt locally. The next FETCH reports these
        IDs to its peer; no send or buffer removal confirms consumption.
        """
