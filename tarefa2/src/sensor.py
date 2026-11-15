from utils.actor_templates.sensor_template import SensorProtocol
from utils.viz_templates.sensor_viz_template import SensorVizMixin
from utils.common.sensor_identity import sensor_id_from_name

class Sensor(SensorVizMixin, SensorProtocol):
    """
    Example Sensor Protocol with added Visualization support.
    If you want to implement your own variation of the protocol,
    add stuff to this class or create another class that inherits
    from SensorProtocol and SensorVizMixin and mix in other
    behaviors you want.
    """
    pass


def make_sensor(name: str) -> type:
    """Bind the configured logical ID independently of simulator node order."""
    logical_id = sensor_id_from_name(name)

    class NamedSensor(Sensor):
        sensor_id = logical_id

    NamedSensor.__name__ = f'Sensor_{logical_id}'
    return NamedSensor
