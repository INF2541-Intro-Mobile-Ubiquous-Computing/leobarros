"""Core UAV requests and peer replication; no receipt ACK."""
import logging

from src.pubsub.models import (
    DeliverEnvelope, FetchEnvelope, Publication, PublishEnvelope,
    ReplicateEnvelope, SubscribeEnvelope, Subscription, SyncEnvelope,
)


class PubSubAdapterMixin:
    def initialize(self) -> None:
        super().initialize()
        self.selected_pspeer = None

    def select_pspeer(self, node_id: int) -> None:
        """Choose one peer by simulator ID; no discovery or shared registry."""
        if type(node_id) is not int or node_id < 0:
            raise ValueError('PSPeer must be a nonnegative node ID')
        self.selected_pspeer = node_id

    def _send_request(self, message) -> bool:
        if self.selected_pspeer is None:
            return False
        return self.send_pubsub(self.selected_pspeer, message)

    def subscribe_pubsub(self, topic, accepted_regions) -> bool:
        node = self.provider.get_id()
        return self._send_request(SubscribeEnvelope(
            node, Subscription(node, topic, accepted_regions)))

    def publish_pubsub(self, publication: Publication) -> bool:
        node = self.provider.get_id()
        if publication.origin_id != node:
            raise ValueError('Publication origin must be this UAV')
        return self._send_request(PublishEnvelope(node, publication))

    def fetch_pubsub(self, topic: str) -> bool:
        node = self.provider.get_id()
        return self._send_request(FetchEnvelope(node, node, topic))

    def handle_pubsub(self, message, source_id: int) -> None:
        node = self.provider.get_id()
        if message.sender_id != source_id:
            return
        if isinstance(message, DeliverEnvelope):
            if source_id == self.selected_pspeer and message.subscriber_id == node:
                logging.info('[PUBSUB client] node=%s peer=%s operation=DELIVER count=%s',
                             node, source_id, len(message.publications))
                self.on_pubsub_delivery(message)
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
            logging.info('[PUBSUB sync] node=%s source=%s version=%s applied=%s',
                         node, source_id, message.version, applied)
            return
        elif isinstance(message, PublishEnvelope):
            if message.publication.origin_id != source_id:
                return
            if service.publish(message.publication):
                self.broadcast_pubsub_replication(ReplicateEnvelope(node, message.publication))
        elif isinstance(message, ReplicateEnvelope):
            inserted = service.publish(message.publication)
            logging.info('[PUBSUB replicate] node=%s source=%s message_id=%s inserted=%s',
                         node, source_id, message.publication.message_id, inserted)
            return  # Never re-broadcast a received replica, even when newly stored.
        elif isinstance(message, FetchEnvelope):
            if message.subscriber_id != source_id:
                return
            publications = service.fetch(source_id, message.topic)
            submitted = self.send_pubsub(source_id, DeliverEnvelope(node, source_id, publications))
            logging.info('[PUBSUB peer] node=%s client=%s response=DELIVER count=%s submitted=%s',
                         node, source_id, len(publications), submitted)
        else:
            return
        logging.info('[PUBSUB peer] node=%s client=%s operation=%s',
                     node, source_id, message.operation.value)

    def on_pubsub_delivery(self, message: DeliverEnvelope) -> None:
        """Client callback for FETCH results, including empty results.

        Receipt does not mark consumption. Repeated FETCH may return the same IDs.
        """
