"""Reproducible, instance-local publication timers for the opt-in star core."""
import logging
import math
import random

from src.pubsub.models import Publication, Region
from utils.common.config import PUBSUB_PUBLICATION_INTERVAL, PUBSUB_SEED, PUBSUB_TOPICS


class CorePublicationMixin:
    initial_core_pspeer_id: int | None = None
    core_publication_timer = 'pubsub_core_publish'

    def initialize(self) -> None:
        super().initialize()
        interval = PUBSUB_PUBLICATION_INTERVAL
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError('PUBSUB_PUBLICATION_INTERVAL must be finite and positive')
        self._core_publication_interval = interval
        node = self.provider.get_id()
        self._core_publication_rng = random.Random(f'{PUBSUB_SEED}:core:{node}')
        self._core_publication_sequence = 0
        peer = node if getattr(self, 'is_pspeer', False) else self.initial_core_pspeer_id
        if peer is not None and not getattr(self, 'mesh_routing', False):
            self.select_pspeer(peer)
        self.provider.schedule_timer(self.core_publication_timer,
                                     self.provider.current_time() + interval)

    def handle_timer(self, timer: str) -> None:
        if timer != self.core_publication_timer:
            return super().handle_timer(timer)
        self._core_publication_sequence += 1
        node = self.provider.get_id()
        publication = Publication(
            f'core:{node}:{self._core_publication_sequence}',
            self._core_publication_rng.choice(PUBSUB_TOPICS), node, Region.C,
            self.provider.current_time(), {'value': self._core_publication_rng.random()})
        submitted = self.publish_pubsub(publication)
        logging.info("[PUBLICATION_SUBMISSION] Core Node %s %s message '%s' for publication on topic %s (origin region: C) to PSPEER %s.",
                     node, 'submitted' if submitted else 'could not submit',
                     publication.message_id, publication.topic, self.selected_pspeer)
        self.provider.schedule_timer(self.core_publication_timer,
                                     self.provider.current_time() + self._core_publication_interval)
