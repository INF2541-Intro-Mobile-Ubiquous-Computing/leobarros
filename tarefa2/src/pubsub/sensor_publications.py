"""Turn satellite sensor batches into queued publications without changing collection."""
import json
import logging

from src.pubsub.models import Publication, Region
from src.satellite import ST_COLLECT_IN, ST_COLLECT_OUT, ST_EXCHANGE
from utils.common.agent_types import AgentType
from utils.common.sensor_identity import sensor_id_from_name, topic_for_sensor


class SensorPublicationMixin:
    sensor_origin_region: str
    initial_pspeer_id: int | None = None

    def initialize(self) -> None:
        super().initialize()
        self._sensor_publication_sequence = 0
        self._pending_sensor_publications = {}
        if self.initial_pspeer_id is not None:
            self.select_pspeer(self.initial_pspeer_id)

    def handle_packet(self, message: str) -> None:
        collecting = self._state in (ST_COLLECT_OUT, ST_COLLECT_IN)
        super().handle_packet(message)  # retain original counters/upload behavior
        if not collecting:
            return
        try:
            raw = json.loads(message)
        except json.JSONDecodeError:
            return
        if not isinstance(raw, dict) or raw.get('sender_type') != AgentType.SENSOR.value:
            return
        packets = raw.get('packets', {})
        if not isinstance(packets, dict):
            return
        for name, count in packets.items():
            try:
                sensor_id = sensor_id_from_name(name)
            except ValueError:
                logging.debug('[PUBSUB sensor] ignoring invalid identity %s', name)
                continue
            if (type(count) is not int or count <= 0
                    or ('sensor_id' in raw and (type(raw['sensor_id']) is not int
                                               or raw['sensor_id'] != sensor_id))):
                continue
            self._sensor_publication_sequence += 1
            publication = Publication(
                f'sensor:{self.provider.get_id()}:{self._sensor_publication_sequence}',
                topic_for_sensor(sensor_id), self.provider.get_id(), Region(self.sensor_origin_region),
                self.provider.current_time(), {'sensor_id': sensor_id, 'packet_count': count})
            self._pending_sensor_publications[publication.message_id] = publication
            logging.info("[MESSAGE_QUEUED] Satellite %s queued message '%s' after receiving data from sensor %s for publication on topic %s (origin region: %s; data packets received: %s).",
                         self.provider.get_id(), publication.message_id, sensor_id,
                         publication.topic, publication.origin_region.value, count)

    def _start_exchange(self, ack_node_id: int) -> None:
        super()._start_exchange(ack_node_id)
        self.flush_sensor_publications()

    def flush_sensor_publications(self) -> None:
        """Submit while in contact; a successful first hop is not a receipt ACK."""
        if self._state != ST_EXCHANGE:
            return
        for message_id, publication in list(self._pending_sensor_publications.items()):
            submitted = self.publish_pubsub(publication)
            if submitted:
                self._pending_sensor_publications.pop(message_id)
            logging.info("[PUBLICATION_SUBMISSION] Satellite %s %s message '%s' to PSPEER %s.",
                         self.provider.get_id(), 'submitted' if submitted else 'could not submit',
                         message_id, self.selected_pspeer)
