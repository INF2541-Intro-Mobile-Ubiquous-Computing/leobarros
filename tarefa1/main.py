from gradysim.simulator.simulation import SimulationBuilder, SimulationConfiguration
from gradysim.simulator.handler.timer import TimerHandler
from gradysim.simulator.handler.visualization import VisualizationHandler
from visible_node_protocol import VisibleNodeProtocol
import math

def main():
    config = SimulationConfiguration(
        duration=10,
        real_time=5.0
    )
    builder = SimulationBuilder(config)
    center = (0, 0, 0)
    radius = 20
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 0)) #1
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 40)) #2
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 80)) #3
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 120)) #4
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 160)) #5
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 200)) #6
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 240)) #7
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 280)) #8
    builder.add_node(VisibleNodeProtocol, positionOnCircle(center, radius, 320)) #9

    builder.add_handler(TimerHandler())
    builder.add_handler(VisualizationHandler())

    simulation = builder.build()
    simulation.start_simulation()

def positionOnCircle(center, radius, angle):
    x_center, y_center, z_center = center
    angle_rad = math.radians(angle)
    x = x_center + radius * math.cos(angle_rad)
    y = y_center + radius * math.sin(angle_rad)
    return (x, y, z_center)

if __name__ == "__main__":
    main()