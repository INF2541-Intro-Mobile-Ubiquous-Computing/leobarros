from visible_node_protocol import VisibleNodeProtocol
from flight_plan import FlightPlan
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
import constants

'''
Nó que pode se mover
'''
class MovableNodeProtocol (VisibleNodeProtocol):

    '''
    Inicialização do nó
    '''
    def initialize(self):
        super().initialize()
        self.flight_plan = FlightPlan(
            list(constants.FLIGHT_PLAN_POINTS), constants.SEGMENT_DURATION
        )
        # Estou contando que main.py adicione os drones em ordem, com IDs de 0 a DRONE_COUNT - 1.
        self.initial_angle = self.provider.get_id() * 360 / constants.DRONE_COUNT
        self.provider.send_mobility_command(SetSpeedMobilityCommand(constants.MOVEMENT_SPEED))
        self.move()
        self.schedule_movement_timer()

    '''
    Tick dos relógios
    '''
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == constants.MOVEMENT_TIMER:
            self.move()
            self.schedule_movement_timer()

    '''
    Programa um timer para movimentação
    '''
    def schedule_movement_timer(self):
        self.provider.schedule_timer(constants.MOVEMENT_TIMER, 
            self.provider.current_time() + constants.MOVEMENT_INTERVAL)

    '''
    Movimenta o drone, calculando a posição do centro virtual e a posição alvo relativa para
    este drone.
    '''
    def move(self):
        t = self.provider.current_time()
        self.center = self.flight_plan.get_position(t)
        # O tempo absoluto mantém a fase da rotação mesmo se um timer atrasar.
        angle = (self.initial_angle + constants.ANGULAR_SPEED * t) % 360
        self.target_position = FlightPlan.position_on_circle(
            self.center, constants.FORMATION_RADIUS, angle
        )
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*self.target_position))
