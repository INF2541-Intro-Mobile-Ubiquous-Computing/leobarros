"""Core-addressed Pub/Sub transport using SwCore radio and neighbor discovery.

The production core uses MeshRoutingMixin's locally computed paths. Standalone
legacy transport retains neighbor/hub forwarding. No global registry or receipt
ACK is used. SwCore's buffer holds isolated Pub/Sub entries until a route returns.
"""
import json
import logging

from src.pubsub.models import Envelope, ReplicateEnvelope, SyncEnvelope, envelope_from_dict
from src.pubsub.radio import ReplicateBroadcastCommand, SyncBroadcastCommand
from utils.common.config import PUBSUB_TRANSPORT_MAX_HOPS


class PubSubTransportMixin:
    transport_msg_type = 'pubsub_core'
    sync_msg_type = 'pubsub_sync'
    replicate_msg_type = 'pubsub_replicate'

    def broadcast_pubsub_replication(self, message: ReplicateEnvelope) -> None:
        """Send one copy to the core; receivers do not forward or acknowledge."""
        source = self.provider.get_id()
        packet = dict(msg_type=self.replicate_msg_type, source_id=source, payload=message.to_dict())
        self.provider.send_communication_command(ReplicateBroadcastCommand(json.dumps(packet)))
        logging.info("[PUBLICATION_BROADCAST] PSPEER %s broadcast message '%s' for replication by other PSPEERs.",
                     source, message.publication.message_id)

    def broadcast_pubsub_sync(self, message: SyncEnvelope) -> None:
        """Send one core-wide SYNC; receivers never forward this packet."""
        source = self.provider.get_id()
        packet = dict(msg_type=self.sync_msg_type, source_id=source, payload=message.to_dict())
        self.provider.send_communication_command(SyncBroadcastCommand(json.dumps(packet)))
        logging.info('[SUBSCRIPTION_BROADCAST] PSPEER %s broadcast %s subscription update(s) to other PSPEERs.',
                     source, len(message.subscriptions))

    def initialize(self) -> None:
        super().initialize()
        self._pubsub_sequence = 0
        self._pubsub_seen: set[str] = set()
        self._pubsub_delivery_state = {}  # transport ID: pending or submitted (never received)

    def _buffered_for(self, sat: int) -> list:
        # The original SwCore callbacks must never serialize Pub/Sub as dock_data.
        return [entry for entry in super()._buffered_for(sat) if 'pubsub_packet' not in entry]

    def _on_connect(self, sat: int, face: str) -> None:
        super()._on_connect(sat, face)
        self._flush_pubsub(sat)

    def _on_rt_update(self, raw: dict) -> None:
        super()._on_rt_update(raw)
        if raw['state'] == 'reachable':
            self._flush_pubsub(raw['sat'])

    def _flush_pubsub(self, sat: int) -> None:
        for key, entry in list(self._core_buffer.items()):
            if entry.get('dest_sat') == sat and 'pubsub_packet' in entry:
                if self._forward_pubsub(entry['pubsub_packet']):
                    self._core_buffer.pop(key, None)

    def _queue_pubsub(self, packet: dict) -> None:
        if packet['payload'].get('operation') == 'DELIVER':
            key = 'pubsub-buffer:' + packet['transport_id']
            self._core_buffer[key] = dict(dest_sat=packet['destination'], pubsub_packet=dict(packet))
            self._pubsub_delivery_state[packet['transport_id']] = 'pending'
            logging.info('[MESSAGE_BUFFERED] node=%s destination=%s state=pending',
                         self.provider.get_id(), packet['destination'])

    def send_pubsub(self, destination: int, message: Envelope) -> bool:
        """Return whether dispatched locally or submitted to the next radio hop.

        True does not confirm destination receipt. Before neighbor discovery or
        without a fresh route, return False; the caller retains responsibility.
        """
        if type(destination) is not int or destination < 0:
            raise ValueError('destination must be a nonnegative node ID')
        payload = message.to_dict()
        self._pubsub_sequence += 1
        source = self.provider.get_id()
        packet = dict(msg_type=self.transport_msg_type,
                      transport_id=f'pubsub:{source}:{self._pubsub_sequence}',
                      source_id=source, destination=destination,
                      hops=0, payload=payload)
        self._pubsub_seen.add(packet['transport_id'])
        if destination == source:
            self.handle_pubsub(envelope_from_dict(payload), source)
            return True
        return self._forward_pubsub(packet)

    def _forward_pubsub(self, packet: dict) -> bool:
        if packet['hops'] >= PUBSUB_TRANSPORT_MAX_HOPS:
            return False
        neighbors = self.fresh_neighbors()
        destination = packet['destination']
        route = self._rt.get(destination)
        if getattr(self, 'mesh_routing', False):
            route = self._mesh_rt.get(destination)
            if (route is None or route['state'] == 'unreachable'
                    or route['next_hop'] == packet.get('sender_id')):
                self._queue_pubsub(packet)
                return False
            next_hop = route['next_hop']
            if route['state'] != 'direct' and next_hop not in neighbors:
                self._queue_pubsub(packet)
                return False
        elif route is not None:
            if route['state'] == 'direct':
                next_hop = destination
            elif (route['state'] == 'hop' and route['next_hop'] in neighbors
                  and route['next_hop'] != packet.get('sender_id')):
                next_hop = route['next_hop']
            else:
                self._queue_pubsub(packet)
                return False  # retained for the next reachable SwCore update
        elif destination in neighbors:
            next_hop = destination
        else:
            hubs = sorted(node for node, entry in neighbors.items()
                          if entry.get('role') == 'hub' and node != packet.get('sender_id'))
            if not hubs:
                return False
            next_hop = hubs[0]
        outgoing = dict(packet, hops=packet['hops'] + 1, next_hop=next_hop)
        logging.debug('[PUBSUB hop] node=%s source=%s destination=%s next=%s hops=%s operation=%s',
                      self.provider.get_id(), packet['source_id'], destination,
                      next_hop, outgoing['hops'], packet['payload']['operation'])
        self._send(outgoing, next_hop)  # SWCoreMixin: real radio unicast
        if packet['payload'].get('operation') == 'DELIVER':
            self._pubsub_delivery_state[packet['transport_id']] = 'submitted'
        return True

    def handle_packet(self, message: str) -> None:
        try:
            packet = json.loads(message)
        except json.JSONDecodeError:
            return super().handle_packet(message)
        if isinstance(packet, dict) and packet.get('msg_type') == self.replicate_msg_type:
            try:
                envelope = envelope_from_dict(packet['payload'])
                source = packet['source_id']
                if (type(source) is int and source >= 0
                        and isinstance(envelope, ReplicateEnvelope)
                        and envelope.sender_id == source):
                    self.handle_pubsub(envelope, source)
            except (KeyError, TypeError, ValueError):
                logging.debug('Discarding malformed Pub/Sub replication packet')
            return
        if isinstance(packet, dict) and packet.get('msg_type') == self.sync_msg_type:
            try:
                envelope = envelope_from_dict(packet['payload'])
                source = packet['source_id']
                if (type(source) is int and source >= 0
                        and isinstance(envelope, SyncEnvelope)
                        and envelope.sender_id == source and envelope.version > 0):
                    self.handle_pubsub(envelope, source)
            except (KeyError, TypeError, ValueError):
                logging.debug('Discarding malformed Pub/Sub SYNC packet')
            return
        if not isinstance(packet, dict) or packet.get('msg_type') != self.transport_msg_type:
            return super().handle_packet(message)
        if packet.get('next_hop') != self.provider.get_id():
            return
        try:
            transport_id = packet['transport_id']
            if not isinstance(transport_id, str) or not transport_id:
                return
            if (type(packet['hops']) is not int
                    or not 1 <= packet['hops'] <= PUBSUB_TRANSPORT_MAX_HOPS
                    or type(packet['destination']) is not int
                    or type(packet['source_id']) is not int):
                return
            envelope = envelope_from_dict(packet['payload'])
        except (KeyError, TypeError, ValueError):
            logging.debug('Discarding malformed Pub/Sub transport packet')
            return
        if transport_id in self._pubsub_seen:
            return
        self._pubsub_seen.add(transport_id)
        if packet['destination'] == self.provider.get_id():
            self.handle_pubsub(envelope, packet['source_id'])
        else:
            self._forward_pubsub(packet)

    def handle_pubsub(self, message: Envelope, source_id: int) -> None:
        """Application receive hook; overridden by a future client/peer layer."""
        logging.debug('[PUBSUB transport] node=%s source=%s operation=%s',
                      self.provider.get_id(), source_id, message.operation.value)
