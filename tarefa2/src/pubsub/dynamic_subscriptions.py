"""Seeded topic/filter changes; offline satellites keep their latest local filters."""
import logging
import math
import random

from src.pubsub.models import Region
from utils.common.config import PUBSUB_SEED, PUBSUB_SUBSCRIPTION_INTERVAL, PUBSUB_TOPICS


class DynamicSubscriptionMixin:
    subscription_timer = 'pubsub_subscribe'

    def initialize(self) -> None:
        super().initialize()
        interval = PUBSUB_SUBSCRIPTION_INTERVAL
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError('PUBSUB_SUBSCRIPTION_INTERVAL must be finite and positive')
        self._subscription_interval = interval
        self._subscription_rng = random.Random(f'{PUBSUB_SEED}:subscriptions:{self.provider.get_id()}')
        self.provider.schedule_timer(self.subscription_timer, self.provider.current_time() + interval)

    def handle_timer(self, timer: str) -> None:
        if timer != self.subscription_timer:
            return super().handle_timer(timer)
        topic = self._subscription_rng.choice(PUBSUB_TOPICS)
        regions = tuple(Region)
        accepted = frozenset(self._subscription_rng.sample(
            regions, self._subscription_rng.randint(1, len(regions))))
        submitted = self.subscribe_pubsub(topic, accepted)
        if submitted:
            self.fetch_pubsub(topic)
        logging.info('[PUBSUB subscription] node=%s topic=%s regions=%s peer=%s submitted=%s',
                     self.provider.get_id(), topic, ','.join(sorted(r.value for r in accepted)),
                     self.selected_pspeer, submitted)
        self.provider.schedule_timer(self.subscription_timer,
                                     self.provider.current_time() + self._subscription_interval)
