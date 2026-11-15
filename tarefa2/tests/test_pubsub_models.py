import json
import unittest

from src.pubsub.models import (
    Publication, Subscription, Region, Operation, SubscribeEnvelope,
    PublishEnvelope, ReplicateEnvelope, FetchEnvelope, DeliverEnvelope, SyncEnvelope,
    envelope_from_dict, envelope_from_json,
)


class PubSubModelsTests(unittest.TestCase):
    def setUp(self):
        self.publication = Publication('uav-12:1', 'T1', 12, Region.N, 2.5,
                                       {'sensor_id': 3, 'values': [1, None, True]})
        self.subscription = Subscription(15, 'T1', {Region.N, Region.C})

    def test_round_trip_all_operations(self):
        envelopes = (
            SubscribeEnvelope(15, self.subscription),
            PublishEnvelope(12, self.publication),
            ReplicateEnvelope(8, self.publication),
            FetchEnvelope(15, 15, 'T1'),
            DeliverEnvelope(8, 15, (self.publication,)),
            SyncEnvelope(8, (self.subscription,)),
        )
        self.assertEqual({item.operation for item in envelopes}, set(Operation))
        for envelope in envelopes:
            with self.subTest(operation=envelope.operation):
                self.assertEqual(envelope_from_json(envelope.to_json()), envelope)
                self.assertEqual(envelope_from_dict(envelope.to_dict()), envelope)
                self.assertEqual(envelope.to_dict()['msg_type'], 'pubsub')

    def test_region_sets_are_copied_deduplicated_and_sorted_on_wire(self):
        regions = {'N', 'C'}
        subscription = Subscription(15, 'T1', regions)
        regions.add('W')
        self.assertEqual(subscription.accepted_regions, frozenset({Region.N, Region.C}))
        first = SubscribeEnvelope(15, subscription)
        second = SubscribeEnvelope(15, Subscription(15, 'T1', ['N', 'C', 'N']))
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(first.to_dict()['subscription']['accepted_regions'], ['C', 'N'])

    def test_all_regions_and_empty_filter(self):
        for region in Region:
            publication = Publication('id', 'T2', 0, region.value, 0, None)
            self.assertEqual(publication.origin_region, region)
        envelope = SubscribeEnvelope(1, Subscription(1, 'T1', set()))
        self.assertEqual(envelope_from_json(envelope.to_json()), envelope)

    def test_invalid_regions_are_rejected(self):
        with self.assertRaises(ValueError):
            Publication('id', 'T1', 1, 'X', 0, {})
        with self.assertRaises(ValueError):
            Subscription(1, 'T1', {'N', 'X'})

    def test_batches_are_copied_and_empty_batches_round_trip(self):
        publications = [self.publication]
        envelope = DeliverEnvelope(8, 15, publications)
        publications.clear()
        self.assertEqual(envelope.publications, (self.publication,))
        for empty in (DeliverEnvelope(8, 15), SyncEnvelope(8)):
            self.assertEqual(envelope_from_json(empty.to_json()), empty)

    def test_serialized_dictionary_does_not_alias_publication_payload(self):
        wire = PublishEnvelope(12, self.publication).to_dict()
        wire['publication']['payload']['values'].append(99)
        self.assertEqual(self.publication.payload['values'], [1, None, True])

    def test_decoder_does_not_mutate_input(self):
        wire = SyncEnvelope(8, (self.subscription,)).to_dict()
        before = json.dumps(wire, sort_keys=True)
        envelope_from_dict(wire)
        self.assertEqual(json.dumps(wire, sort_keys=True), before)

    def test_invalid_envelopes_are_rejected(self):
        valid = FetchEnvelope(15, 15, 'T1').to_dict()
        cases = [{}, {**valid, 'msg_type': 'routing_swcore'},
                 {**valid, 'operation': 'UNKNOWN'}, {**valid, 'extra': 1},
                 {key: value for key, value in valid.items() if key != 'topic'}]
        for wire in cases:
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                envelope_from_dict(wire)
        for message in ('[]', 'null', '{', '{"value": NaN}'):
            with self.subTest(message=message), self.assertRaises(ValueError):
                envelope_from_json(message)

    def test_non_json_payloads_fail_before_transmission(self):
        for payload in (object(), float('nan'), float('inf')):
            with self.subTest(payload=payload), self.assertRaises((TypeError, ValueError)):
                PublishEnvelope(1, Publication('id', 'T1', 1, 'C', 0, payload)).to_json()


if __name__ == '__main__':
    unittest.main()
