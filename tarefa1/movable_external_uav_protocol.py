"""Movimento axial dos satélites entre a bounding box e o ponto de retorno."""
import math

from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
from visible_node_protocol import VisibleNodeProtocol
from flight_plan import FlightPlan
import constants


class MovableExternalUAVProtocol(VisibleNodeProtocol):
    target_index = None
    external_index = None

    @classmethod
    def with_target(cls, index):
        class ConfiguredExternalUAV(cls):
            target_index = index
        return ConfiguredExternalUAV

    @classmethod
    def with_external(cls, index):
        class ConfiguredExternalUAV(cls):
            external_index = index
        return ConfiguredExternalUAV

    @staticmethod
    def station_position(index, away=False):
        direction = constants.EXTERNAL_DIRECTIONS[index]
        distance = constants.FORMATION_RADIUS + constants.EXTERNAL_CONTACT_OFFSET
        if away:
            distance += constants.EXTERNAL_AWAY_DISTANCE
        return tuple(c + distance * d for c, d in zip(FlightPlan.get_position(0), direction))

    def initialize(self):
        self.flight_plan = FlightPlan(constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT)
        if self.external_index is None:
            target = self.target_index if self.target_index is not None else constants.EXTERNAL_TARGET_INDEX
            self.external_index = next((i for i, t in constants.EXTERNAL_CORE_TARGETS.items() if t == target), 0)
        if self.external_index not in constants.EXTERNAL_DIRECTIONS:
            raise ValueError('Lado da bounding box inválido.')
        mailbox = self.flight_plan.get_core_target(self.external_index)
        self.color = constants.PAIR_COLORS.get(mailbox, constants.DEFAULT_COLOR)
        self.target_index = None
        for value in (constants.EXTERNAL_SPEED, constants.EXTERNAL_AWAY_DISTANCE,
                      constants.EXTERNAL_CONTACT_DISTANCE):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Os parâmetros de movimento externo devem ser positivos e finitos.')
        if not 0 <= constants.SAFETY_MARGIN < constants.EXTERNAL_CONTACT_OFFSET < constants.EXTERNAL_CONTACT_DISTANCE:
            raise ValueError('Use margem de segurança < afastamento da caixa < distância de contato.')
        self.current_position = None
        self.mode = None
        self.destination = None
        self.contact_point = self.station_position(self.external_index)
        self.away_point = self.station_position(self.external_index, away=True)
        super().initialize()
        self.provider.send_mobility_command(SetSpeedMobilityCommand(constants.EXTERNAL_SPEED))
        self.schedule_movement_timer()

    def contact_position(self, time):
        return self.contact_point

    def at_contact_point(self):
        return self.current_position is not None and math.dist(self.current_position, self.contact_point) <= 1e-6

    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position
        self.advance_movement(self.provider.current_time())

    def advance_movement(self, now):
        if self.mode is None:
            self.start_seek(now)
        if self.mode == 'away' and math.dist(self.current_position, self.away_point) <= 1e-6:
            self.start_seek(now)
        if self.mode == 'seek' and self.at_contact_point():
            self.mode = 'waiting'
            self.steer(self.contact_point, now)
        if self.mode == 'waiting':
            self.wait_for_core(now)

    def wait_for_core(self, now):
        """O protocolo de comunicação confirma o encontro e libera a partida."""
        pass

    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == constants.MOVEMENT_TIMER:
            if self.current_position is not None:
                self.advance_movement(self.provider.current_time())
            self.schedule_movement_timer()

    def schedule_movement_timer(self):
        self.provider.schedule_timer(constants.MOVEMENT_TIMER,
                                     self.provider.current_time() + constants.MOVEMENT_INTERVAL)

    def start_seek(self, now):
        self.mode = 'seek'
        self.target_index = None
        self.steer(self.contact_point, now)

    def start_away(self, now):
        self.mode = 'away'
        self.target_index = None
        self.steer(self.away_point, now)

    def steer(self, destination, now):
        # Os dois destinos fixos ficam no mesmo eixo; nunca há perseguição lateral.
        self.destination = destination
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*destination))
