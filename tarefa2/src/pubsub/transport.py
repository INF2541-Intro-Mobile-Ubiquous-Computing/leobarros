"""Core-addressed Pub/Sub transport using SwCore radio and neighbor discovery.

The supported topology is star: send to a known neighbor or through the known
hub. No global node registry, extra discovery flood, ACK or retry is used.
Satellite-addressed application delivery is left to the later integration step.
"""
import json
import logging

from src.pubsub.models import Envelope, envelope_from_dict
from utils.common.config import PUBSUB_TRANSPORT_MAX_HOPS


class PubSubTransportMixin:
    transport_msg_type = 'pubsub_core'

    def initialize(self) -> None:
        super().initialize()
        self._pubsub_sequence = 0
        self._pubsub_seen: set[str] = set()

    def send_pubsub(self, destination: int, message: Envelope) -> bool:
        """Return whether dispatched locally or submitted to the next radio hop.

        True does not confirm destination receipt. Before neighbor discovery or
        without a fresh route, return False; the caller retains responsibility.
        """
        if type(destination) is not int or destination < 0:
            raise ValueError('destination must be a nonnegative core node ID')
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
        if destination in neighbors:
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
        return True

    def handle_packet(self, message: str) -> None:
        try:
            packet = json.loads(message)
        except json.JSONDecodeError:
            return super().handle_packet(message)
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
