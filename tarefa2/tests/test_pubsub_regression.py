"""Cross-operation regressions for the local Pub/Sub model."""
from itertools import permutations
import unittest

from src.pubsub.models import Publication, Region, Subscription
from src.pubsub.pspeer_service import PSPeerService


def publication(message_id, region=Region.N, topic='T1'):
    return Publication(message_id, topic, 12, region, 1.0, {'value': 42})


class PubSubRegressionTests(unittest.TestCase):
    def test_subscription_timing_does_not_lose_history_in_any_operation_order(self):
        # All six orders: subscription before, between or after publications.
        for order in permutations(('subscribe', 'first', 'second')):
            with self.subTest(order=order):
                service = PSPeerService()
                arrived = []
                subscribed = False
                for operation in order:
                    if operation == 'subscribe':
                        service.subscribe(Subscription(10, 'T1', {Region.N}))
                        subscribed = True
                    else:
                        item = publication(operation)
                        service.publish(item)
                        arrived.append(item)
                    expected = tuple(arrived) if subscribed else ()
                    self.assertEqual(service.fetch(10, 'T1'), expected)
                    self.assertEqual(service.fetch(10, 'T1'), expected)
                self.assertEqual(service.fetch(10, 'T1'), tuple(arrived))

    def test_replay_after_consumption_does_not_resurrect_or_overwrite_messages(self):
        service = PSPeerService()
        subscription = Subscription(10, 'T1', {Region.N, Region.E})
        first, pending = publication('read'), publication('pending', Region.E)
        service.subscribe(subscription)
        service.publish(first)
        service.publish(pending)
        service.mark_consumed(10, 'T1', 'read')
        # Different replay orders must keep both stored content and read state.
        for order in permutations(('subscribe', 'publication', 'confirmation')):
            with self.subTest(order=order):
                for operation in order:
                    if operation == 'subscribe':
                        self.assertFalse(service.subscribe(subscription))
                    elif operation == 'publication':
                        self.assertFalse(service.publish(publication('read', Region.E)))
                        self.assertFalse(service.publish(publication('pending', topic='T2')))
                    else:
                        self.assertFalse(service.mark_consumed(10, 'T1', 'read'))
                    self.assertEqual(service.fetch(10, 'T1'), (pending,))
        service.subscribe(Subscription(11, 'T1', {Region.N, Region.E}))
        service.subscribe(Subscription(10, 'T2', set(Region)))
        self.assertEqual(service.fetch(11, 'T1'), (first, pending))
        self.assertEqual(service.fetch(10, 'T2'), ())

    def test_filter_narrowing_expansion_and_late_receipt_keep_exact_unread_ids(self):
        service = PSPeerService()
        for item in (publication('n'), publication('e', Region.E),
                     publication('c', Region.C), publication('t2', topic='T2')):
            service.publish(item)
        service.subscribe(Subscription(10, 'T2', {Region.N}))
        steps = (
            ({Region.N}, ['n']),
            ({Region.E}, ['e']),
            (set(), []),
            ({Region.N, Region.E, Region.C}, ['n', 'e', 'c']),
        )
        for regions, expected in steps:
            service.subscribe(Subscription(10, 'T1', regions))
            self.assertEqual([p.message_id for p in service.fetch(10, 'T1')], expected)
        service.subscribe(Subscription(10, 'T1', {Region.E}))
        # Receipt of N confirmed after the filter changed, not on FETCH.
        self.assertTrue(service.mark_consumed(10, 'T1', 'n'))
        service.publish(publication('new', Region.C))
        service.subscribe(Subscription(10, 'T1', set(Region)))
        self.assertEqual([p.message_id for p in service.fetch(10, 'T1')], ['e', 'c', 'new'])
        self.assertEqual([p.message_id for p in service.fetch(10, 'T2')], ['t2'])


if __name__ == '__main__':
    unittest.main()
