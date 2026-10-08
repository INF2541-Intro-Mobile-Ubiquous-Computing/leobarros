from visible_node_protocol import VisibleNodeProtocol
from flight_plan import FlightPlan
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
import math
import random
import constants

class MovableExternalUAVProtocol (VisibleNodeProtocol):

    target_index = None

    @classmethod
    def with_target(cls, index):
        """O builder recebe uma classe; cria uma configuração para este alvo."""
        class ConfiguredExternalUAV(cls):
            target_index = index

        return ConfiguredExternalUAV

    def initialize(self):
        super().initialize()
        if self.target_index is None:
            self.target_index = constants.EXTERNAL_TARGET_INDEX
        if not 0 <= self.target_index < constants.DRONE_COUNT:
            raise ValueError('Índice do alvo externo fora do core.')
        for value in (constants.EXTERNAL_SPEED, constants.EXTERNAL_AWAY_DURATION,
                      constants.EXTERNAL_CONTACT_DISTANCE, constants.EXTERNAL_INTERCEPT_STEP):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Os parâmetros de movimento externo devem ser positivos e finitos.')
        self.flight_plan = FlightPlan(constants.FLIGHT_PLAN_POINTS, constants.CENTER_SPEED)
        self.current_position = None
        self.mode = None
        self.provider.send_mobility_command(SetSpeedMobilityCommand(constants.EXTERNAL_SPEED))
        self.schedule_movement_timer()

    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position
        now = self.provider.current_time()
        # A posição inicial vem da telemetria, após ser definida no main.py.
        if self.mode is None:
            self.start_away(now)
        elif self.mode == 'seek' and self.in_contact(now):
            self.start_away(now)

    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer != constants.MOVEMENT_TIMER:
            return
        now = self.provider.current_time()
        if self.current_position is not None:
            if self.mode == 'away' and now >= self.away_until:
                self.mode = 'seek'
            if self.mode == 'seek':
                if self.in_contact(now):
                    self.start_away(now)
                else:
                    destination = self.find_intercept(now)
                    self.provider.send_mobility_command(GotoCoordsMobilityCommand(*destination))
        self.schedule_movement_timer()

    def schedule_movement_timer(self):
        deadline = self.provider.current_time() + constants.MOVEMENT_INTERVAL
        if self.mode == 'away':
            deadline = min(deadline, self.away_until)
        self.provider.schedule_timer(constants.MOVEMENT_TIMER, deadline)

    def start_away(self, now):
        self.mode = 'away'
        self.away_until = now + constants.EXTERNAL_AWAY_DURATION
        center = self.flight_plan.get_position(now)
        x, y, z = self.current_position
        outward_angle = math.atan2(y - center[1], x - center[0])
        angle = outward_angle + random.uniform(-math.pi / 2, math.pi / 2)
        # Um único destino mantém a direção sorteada durante todo o afastamento.
        distance = constants.EXTERNAL_SPEED * (constants.EXTERNAL_AWAY_DURATION + constants.MOVEMENT_INTERVAL)
        destination = (x + distance * math.cos(angle), y + distance * math.sin(angle), z)
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*destination))

    def target_position(self, time):
        center = self.flight_plan.get_position(time)
        angle = self.target_index * 360 / constants.DRONE_COUNT + constants.ANGULAR_SPEED * time
        return FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS, angle)

    def in_contact(self, now):
        return math.dist(self.current_position, self.target_position(now)) <= constants.EXTERNAL_CONTACT_DISTANCE

    def find_intercept(self, now):
        """Primeiro encontro viável na grade temporal; retorna a borda de contato.

        Em t segundos, o UAV percorre EXTERNAL_SPEED * t metros. Basta chegar
        à esfera de contato do alvo previsto, não ao próprio alvo. Como o plano
        é limitado, a busca termina mesmo se o alvo for mais rápido que o UAV.
        """
        delay = 0.0
        while True:
            target = self.target_position(now + delay)
            distance = math.dist(self.current_position, target)
            travel_distance = max(0.0, distance - constants.EXTERNAL_CONTACT_DISTANCE)
            if travel_distance <= constants.EXTERNAL_SPEED * delay:
                fraction = travel_distance / distance if distance else 0.0
                return tuple(p + fraction * (q - p) for p, q in zip(self.current_position, target))
            delay += constants.EXTERNAL_INTERCEPT_STEP
