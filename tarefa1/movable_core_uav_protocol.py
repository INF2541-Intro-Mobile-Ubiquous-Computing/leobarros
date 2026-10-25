from visible_node_protocol import VisibleNodeProtocol
from flight_plan import FlightPlan
from random_core_motion import RandomCoreMotion
import math
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
import constants

'''
Classe responsável pela mobilidade de um drone do Core
'''
class MovableCoreUAVProtocol (VisibleNodeProtocol):

    '''
    Inicialização do nó
    '''
    def initialize(self):
        if constants.SIMULATION_MODE not in (constants.TOPOLOGY, constants.RANDOM):
            raise ValueError('SIMULATION_MODE deve ser TOPOLOGY ou RANDOM.')
        self.simulation_mode = constants.SIMULATION_MODE
        self.color = constants.PAIR_COLORS.get(self.provider.get_id(), constants.DEFAULT_COLOR)
        super().initialize()
        self.flight_plan = FlightPlan(
            constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT
        )
        # Estou contando que main.py adicione os drones em ordem, com IDs de 0 a DRONE_COUNT - 1.
        self.initial_angle = self.provider.get_id() * 360 / constants.DRONE_COUNT
        if self.simulation_mode == constants.RANDOM:
            if not math.isfinite(constants.RANDOM_MOVEMENT_INTERVAL) or constants.RANDOM_MOVEMENT_INTERVAL <= 0:
                raise ValueError('RANDOM_MOVEMENT_INTERVAL deve ser positivo e finito.')
            self.random_motion = RandomCoreMotion(constants.FORMATION_RADIUS, constants.RANDOM_SPEED,
                                                  constants.RANDOM_DIRECTION_INTERVAL, self.initial_angle)
            self.current_position = FlightPlan.position_on_circle(
                self.flight_plan.get_position(0), constants.FORMATION_RADIUS, self.initial_angle)
            self.move_random()
            return
        self.provider.send_mobility_command(SetSpeedMobilityCommand(constants.MOVEMENT_SPEED))
        self.move()
        self.schedule_movement_timer()

    def handle_telemetry(self, telemetry):
        if self.simulation_mode == constants.RANDOM:
            self.current_position = telemetry.current_position
            self.move_random()

    def move_random(self):
        # Mira a próxima atualização física no disco de centro fixo.
        # A velocidade exata do passo evita atraso que deixaria o nó fora do disco.
        time = self.provider.current_time() + constants.RANDOM_MOVEMENT_INTERVAL
        self.center = self.flight_plan.get_position(time)
        x, y = self.random_motion.position_at(time)
        self.target_position = (self.center[0] + x, self.center[1] + y, self.center[2])
        speed = math.dist(self.current_position, self.target_position) / constants.RANDOM_MOVEMENT_INTERVAL
        self.provider.send_mobility_command(SetSpeedMobilityCommand(speed))
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*self.target_position))

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
