"""Run only the local model suite: python -B tests/run_pubsub_tests.py."""
from pathlib import Path
import sys
import unittest


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))

MODEL_TESTS = (
    'test_subscription_sync.py',
    'test_pubsub_models.py',
    'test_topic_store.py',
    'test_subscription_store.py',
    'test_consumption_store.py',
    'test_pspeer_service.py',
    'test_pubsub_regression.py',
)


def main() -> int:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for filename in MODEL_TESTS:
        suite.addTests(loader.discover(str(TESTS), pattern=filename))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if any(name == 'gradysim' or name.startswith('gradysim.') for name in sys.modules):
        print('ERROR: local Pub/Sub tests imported GrADyS-SIM.', file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
