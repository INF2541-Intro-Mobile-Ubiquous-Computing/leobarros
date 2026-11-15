import unittest

from src.pubsub.models import Publication, Region, Subscription
from src.pubsub.pspeer_service import PSPeerService


def publication(message_id, region=Region.N, topic='T1'):
    return Publication(message_id, topic, 12, region, 1.0, {'value': 42})


class PSPeerServiceTests(unittest.TestCase):
    def test_complete_local_subscribe_publish_fetch_consume_cycle(self):
        service = PSPeerService()
        self.assertTrue(service.subscribe(Subscription(10, 'T1', {Region.N, Region.S})))
        north = publication('north')
        south = publication('south', Region.S)
        for item in (north, publication('east', Region.E), south,
                     publication('other-topic', topic='T2')):
            self.assertTrue(service.publish(item))
        self.assertEqual(service.fetch(10, 'T1'), (north, south))
        self.assertEqual(service.fetch(10, 'T1'), (north, south))
        self.assertTrue(service.mark_consumed(10, 'T1', 'north'))
        self.assertEqual(service.fetch(10, 'T1'), (south,))
        self.assertTrue(service.mark_consumed(10, 'T1', 'south'))
        self.assertEqual(service.fetch(10, 'T1'), ())

    def test_history_before_subscription_and_filter_update_preserve_consumption(self):
        service = PSPeerService()
        north, east = publication('north'), publication('east', Region.E)
        service.publish(north)
        service.publish(east)
        self.assertEqual(service.fetch(10, 'T1'), ())
        service.subscribe(Subscription(10, 'T1', {Region.N}))
        self.assertEqual(service.fetch(10, 'T1'), (north,))
        service.mark_consumed(10, 'T1', 'north')
        service.subscribe(Subscription(10, 'T1', {Region.N, Region.E}))
        self.assertEqual(service.fetch(10, 'T1'), (east,))
        new = publication('new')
        service.publish(new)
        self.assertEqual(service.fetch(10, 'T1'), (east, new))

    def test_repeated_operations_and_invalid_consumption_do_not_change_results(self):
        service = PSPeerService()
        subscription = Subscription(10, 'T1', {Region.N})
        service.subscribe(subscription)
        self.assertFalse(service.subscribe(subscription))
        item = publication('one')
        self.assertTrue(service.publish(item))
        self.assertFalse(service.publish(publication('one', Region.E, 'T2')))
        self.assertFalse(service.mark_consumed(99, 'T1', 'one'))
        self.assertFalse(service.mark_consumed(10, 'T1', 'missing'))
        self.assertFalse(service.mark_consumed(10, 'T2', 'one'))
        self.assertEqual(service.fetch(10, 'T1'), (item,))
        self.assertTrue(service.mark_consumed(10, 'T1', 'one'))
        self.assertFalse(service.mark_consumed(10, 'T1', 'one'))

    def test_subscribers_and_topics_keep_separate_consumption(self):
        service = PSPeerService()
        first, second = publication('first'), publication('second', topic='T2')
        for subscriber in (10, 11):
            for topic in ('T1', 'T2'):
                service.subscribe(Subscription(subscriber, topic, {Region.N}))
        service.publish(first)
        service.publish(second)
        service.mark_consumed(10, 'T1', 'first')
        self.assertEqual(service.fetch(10, 'T1'), ())
        self.assertEqual(service.fetch(11, 'T1'), (first,))
        self.assertEqual(service.fetch(10, 'T2'), (second,))

    def test_peers_have_independent_publications_subscriptions_and_consumption(self):
        first, second = PSPeerService(), PSPeerService()
        item = publication('one')
        first.publish(item)
        first.subscribe(Subscription(10, 'T1', {Region.N}))
        self.assertEqual(second.fetch(10, 'T1'), ())
        second.subscribe(Subscription(10, 'T1', {Region.N}))
        self.assertEqual(second.fetch(10, 'T1'), ())
        self.assertTrue(second.publish(item))
        first.mark_consumed(10, 'T1', 'one')
        self.assertEqual(second.fetch(10, 'T1'), (item,))
        second.subscribe(Subscription(10, 'T1', {Region.E}))
        new = publication('new')
        first.publish(new)
        self.assertEqual(first.fetch(10, 'T1'), (new,))


if __name__ == '__main__':
    unittest.main()
