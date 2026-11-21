"""Opt-in Pub/Sub at an existing satellite contact; no movement or retry changes."""
import json

from gradysim.protocol.messages.communication import SendMessageCommand

from src.pubsub.adapter import PubSubAdapterMixin
from src.pubsub.transport import PubSubTransportMixin
from src.pubsub.events import pubsub_event
from src.satellite import ST_EXCHANGE, ST_WAIT_ALIGN
from utils.common.config import PUBSUB_TRANSPORT_MAX_HOPS


class PubSubSatelliteMixin(PubSubAdapterMixin, PubSubTransportMixin):
    def handle_packet(self, message: str) -> None:
        try:
            packet = json.loads(message)
        except json.JSONDecodeError:
            return super().handle_packet(message)
        if (isinstance(packet, dict) and packet.get('msg_type') == 'dock_ack'
                and packet.get('face') == self.sensor_origin_region
                and self._state == ST_WAIT_ALIGN and self._ack_node is None
                and 'pspeer_id' in packet):
            peer = packet['pspeer_id']
            if peer is not None and (type(peer) is not int or peer < 0):
                return
            # Resume only after the handshake has entered EXCHANGE.
            self.selected_pspeer = peer
        return super().handle_packet(message)

    def _subscription_failure_reason(self) -> str:
        if self.selected_pspeer is None:
            return super()._subscription_failure_reason()
        if self._state != ST_EXCHANGE:
            return 'the satellite has not entered data exchange with the core; its subscription is retained locally for the next contact'
        if self._ack_node is None:
            return 'no core contact has been confirmed; its subscription is retained locally for the next contact'
        return super()._subscription_failure_reason()

    def _start_exchange(self, ack_node_id: int) -> None:
        super()._start_exchange(ack_node_id)
        pubsub_event(self, 'contact_started', contact=ack_node_id, peer=self.selected_pspeer,
                     region=getattr(self, 'sensor_origin_region', None),
                     completed_cycles=getattr(self, '_dock_count', 0))
        self.resume_pubsub()

    def _forward_pubsub(self, packet: dict) -> bool:
        # Satellites originate requests only; they never relay core traffic.
        if (self._state != ST_EXCHANGE or self._ack_node is None
                or packet['source_id'] != self.provider.get_id()
                or packet['hops'] >= PUBSUB_TRANSPORT_MAX_HOPS):
            return False
        outgoing = dict(packet, hops=packet['hops'] + 1, next_hop=self._ack_node,
                        sender_id=self.provider.get_id())
        self.provider.send_communication_command(SendMessageCommand(json.dumps(outgoing), self._ack_node))
        return True

    def handle_pubsub(self, message, source_id: int) -> None:
        if self._state == ST_EXCHANGE:
            super().handle_pubsub(message, source_id)
