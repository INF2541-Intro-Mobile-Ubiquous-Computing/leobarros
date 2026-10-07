from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler
from visible_node_protocol import VisibleNodeProtocol
from movable_node_protocol import MovableNodeProtocol
from flight_plan import FlightPlan
import math

def main():
    config = SimulationConfiguration(
        duration=10
    )
    builder = SimulationBuilder(config)
    center = (0, 0, 0)
    radius = 20
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 0)) #1
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 40)) #2
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 80)) #3
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 120)) #4
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 160)) #5
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 200)) #6
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 240)) #7
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 280)) #8
    builder.add_node(MovableNodeProtocol, position_on_circle(center, radius, 320)) #9

    flight_plan = FlightPlan(
        points=[
            (0, 0, 0),
            (100, 0, 0),
            (100, 50, 0),
            (0, 50, 0)
        ],
        segment_duration=10
    )

    print(flight_plan.get_position(0))
    # (0.0, 0.0, 0)

    print(flight_plan.get_position(5))
    # (50.0, 0.0, 0)

    print(flight_plan.get_position(10))
    # (100.0, 0.0, 0)

    print(flight_plan.get_position(15))
    # (100.0, 25.0, 0)

    print(flight_plan.get_position(40))
    # voltou ao início do ciclo
    # (0.0, 0.0, 0)

    builder.add_handler(TimerHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

def position_on_circle(center, radius, angle):
    x_center, y_center, z_center = center
    angle_rad = math.radians(angle)
    x = x_center + radius * math.cos(angle_rad)
    y = y_center + radius * math.sin(angle_rad)
    return (x, y, z_center)

if __name__ == "__main__":
    main()