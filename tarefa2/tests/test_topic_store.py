"""History ordering, deduplication and isolation contracts for TopicStore."""
from dataclasses import replace
import unittest

from src.pubsub.models import Publication, Region
from src.pubsub.topic_store import TopicStore


def publication(message_id='m1', topic='T1', created_at=10.0):
    return Publication(message_id, topic, 12, Region.N, created_at,
                       {'readings': [1, {'value': 2}]})


class TopicStoreTests(unittest.TestCase):
    def test_empty_topic_and_first_insertion(self):
        store = TopicStore()
        self.assertEqual(store.get_history('T1'), ())
        item = publication()
        self.assertTrue(store.add_publication(item))
        self.assertEqual(store.get_history('T1'), (item,))
        self.assertEqual(store.get_history('unknown'), ())

    def test_arrival_order_is_not_creation_time_order(self):
        store = TopicStore()
        items = [publication('m1', created_at=30), publication('m2', created_at=5),
                 publication('m3', created_at=30)]
        for item in items:
            store.add_publication(item)
        history = store.get_history('T1')
        self.assertEqual(history, tuple(items))
        self.assertEqual([item.created_at for item in history], [30, 5, 30])

    def test_interleaved_topics_keep_separate_histories(self):
        store = TopicStore()
        first, second, third = publication('a'), publication('b', 'T2'), publication('c')
        for item in (first, second, third):
            store.add_publication(item)
        self.assertEqual(store.get_history('T1'), (first, third))
        self.assertEqual(store.get_history('T2'), (second,))

    def test_duplicate_does_not_append_or_move_original(self):
        store = TopicStore()
        first, second = publication('a'), publication('b')
        store.add_publication(first)
        store.add_publication(second)
        self.assertFalse(store.add_publication(first))
        self.assertEqual(store.get_history('T1'), (first, second))

    def test_conflicting_duplicate_preserves_first_publication_across_topics(self):
        store = TopicStore()
        first = publication()
        store.add_publication(first)
        for conflict in (replace(first, payload={'other': True}, created_at=99),
                         replace(first, topic='T2', origin_id=20, origin_region=Region.C)):
            self.assertFalse(store.add_publication(conflict))
        self.assertEqual(store.get_history('T1'), (first,))
        self.assertEqual(store.get_history('T2'), ())

    def test_distinct_ids_with_identical_content_are_not_duplicates(self):
        store = TopicStore()
        first = publication()
        second = replace(first, message_id='m2')
        self.assertTrue(store.add_publication(first))
        self.assertTrue(store.add_publication(second))
        self.assertEqual(store.get_history('T1'), (first, second))

    def test_mutating_input_or_query_payload_cannot_change_stored_history(self):
        store = TopicStore()
        original = publication()
        store.add_publication(original)
        original.payload['readings'][1]['value'] = 99
        snapshot = store.get_history('T1')
        self.assertEqual(snapshot[0].payload['readings'][1]['value'], 2)
        snapshot[0].payload['readings'].append(100)
        self.assertEqual(store.get_history('T1')[0].payload,
                         {'readings': [1, {'value': 2}]})

    def test_history_snapshot_does_not_grow_after_new_arrival(self):
        store = TopicStore()
        first = publication()
        store.add_publication(first)
        snapshot = store.get_history('T1')
        store.add_publication(publication('m2'))
        self.assertEqual(snapshot, (first,))
        self.assertEqual(len(store.get_history('T1')), 2)

    def test_instances_have_independent_histories_and_deduplication(self):
        first, second = TopicStore(), TopicStore()
        item = publication()
        first.add_publication(item)
        self.assertEqual(second.get_history('T1'), ())
        self.assertTrue(second.add_publication(item))
        first.add_publication(publication('m2'))
        self.assertEqual(second.get_history('T1'), (item,))


if __name__ == '__main__':
    unittest.main()
