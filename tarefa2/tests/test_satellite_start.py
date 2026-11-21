"""Specification v2: satellites approach from the four outer cardinal points."""
import math
import unittest
from unittest.mock import Mock, patch

from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand
from src import main
from src.satellite import ST_COLLECT_IN, ST_COLLECT_OUT
from src.uav import make_satellite
from utils.common.config import (
    FACE_NAMES, OBSTACLE_CENTER, SAT_OUTER_DIST, dock_point_of, sat_start,
)


class SatelliteStartTests(unittest.TestCase):
    def test_pubsub_starts_away_and_first_leg_approaches_dock(self):
        for face in FACE_NAMES:
            with self.subTest(face=face):
                node = make_satellite(face, swcore=True, pubsub=True)()
                node.provider = Mock()
                node.provider.get_id.return_value = 100 + FACE_NAMES.index(face)
                node.provider.current_time.return_value = 0.0
                node.initialize()
                start = sat_start(face, start_away=True)
                self.assertEqual(node._current_position, start)
                self.assertEqual(node._state, ST_COLLECT_IN)
                self.assertAlmostEqual(math.dist(start[:2], OBSTACLE_CENTER), SAT_OUTER_DIST)
                self.assertTrue(abs(start[0] - OBSTACLE_CENTER[0]) < 1e-10
                                or abs(start[1] - OBSTACLE_CENTER[1]) < 1e-10)
                moves = [call.args[0] for call in node.provider.send_mobility_command.call_args_list
                         if isinstance(call.args[0], GotoCoordsMobilityCommand)]
                self.assertEqual(len(moves), 1)
                self.assertEqual(moves[0], GotoCoordsMobilityCommand(*dock_point_of(face), start[2]))

    def test_legacy_start_is_preserved(self):
        node = make_satellite('N')()
        node.provider = Mock()
        node.provider.current_time.return_value = 0.0
        node.initialize()
        self.assertEqual(node._state, ST_COLLECT_OUT)
        self.assertEqual(node._current_position, sat_start('N'))

    def test_builder_and_protocol_agree_on_initial_position(self):
        with (patch('sys.argv', ['main', '--pubsub', '--no-viz']),
              patch.object(main, 'SimulationBuilder') as builder):
            main.main()
        calls = builder.return_value.add_node.call_args_list[-4:]
        self.assertEqual([call.args[1] for call in calls],
                         [sat_start(face, start_away=True) for face in FACE_NAMES])
