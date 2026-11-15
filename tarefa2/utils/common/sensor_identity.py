"""Stable logical sensor IDs and topic selection; no publication generation."""
from utils.common.config import SENSOR_TOPIC_BY_PARITY


def sensor_id_from_name(name: str) -> int:
    """Read the canonical sensor_N key used by SENSOR_POSITIONS."""
    if not isinstance(name, str) or not name.startswith('sensor_'):
        raise ValueError('Expected canonical sensor_N name')
    try:
        sensor_id = int(name[7:])
    except ValueError as exc:
        raise ValueError('Expected canonical sensor_N name') from exc
    if sensor_id < 0 or name != f'sensor_{sensor_id}':
        raise ValueError('Expected canonical nonnegative sensor_N name')
    return sensor_id


def topic_for_sensor(sensor_id: int) -> str:
    if type(sensor_id) is not int or sensor_id < 0:
        raise ValueError('sensor_id must be a nonnegative integer')
    return SENSOR_TOPIC_BY_PARITY[sensor_id % 2]
