from visible_node_protocol import VisibleNodeProtocol
from flight_plan import FlightPlan
from gradysim.protocol.messages.mobility import GotoCoordsMobilityCommand, SetSpeedMobilityCommand
import math
import random
import constants

class MovableExternalUAVProtocol (VisibleNodeProtocol):

    target_index = None
    external_index = None

    @classmethod
    def with_target(cls, index):
        """O builder recebe uma classe; cria uma configuração para este alvo."""
        class ConfiguredExternalUAV(cls):
            target_index = index

        return ConfiguredExternalUAV

    def initialize(self):
        self.flight_plan = FlightPlan(
            constants.FLIGHT_PLAN_POINTS, constants.CENTER_SPEED,
            constants.EXTERNAL_CORE_TARGETS, constants.DRONE_COUNT)
        if self.external_index is not None:
            self.target_index = self.flight_plan.get_core_target(self.external_index)
        if self.target_index is None:
            self.target_index = constants.EXTERNAL_TARGET_INDEX
        self.color = constants.PAIR_COLORS.get(self.target_index, constants.DEFAULT_COLOR)
        super().initialize()
        if not 0 <= self.target_index < constants.DRONE_COUNT:
            raise ValueError('Índice do alvo externo fora do core.')
        for value in (constants.EXTERNAL_SPEED, constants.EXTERNAL_AWAY_DURATION,
                      constants.EXTERNAL_CONTACT_DISTANCE, constants.EXTERNAL_INTERCEPT_STEP):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Os parâmetros de movimento externo devem ser positivos e finitos.')
        if (constants.SIMULATION_MODE != constants.RANDOM
                and not 0 < constants.SAFETY_MARGIN < constants.EXTERNAL_CONTACT_OFFSET < constants.EXTERNAL_CONTACT_DISTANCE):
            raise ValueError('Use 0 < margem de segurança < afastamento de contato < alcance de contato.')
        if constants.EXTERNAL_SPEED <= constants.CENTER_SPEED:
            raise ValueError('O UAV externo deve ser mais rápido que o centro para conseguir se afastar.')
        self.current_position = None
        self.mode = None
        self.contour_direction = None
        self.destination = None
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
        elif self.destination is not None and not self.path_is_safe(self.destination, now):
            self.steer(self.destination, now)

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
                    self.steer(destination, now)
            else:
                # Mantém a direção sorteada, salvo quando a segurança exige desvio.
                distance = constants.EXTERNAL_SPEED * (constants.MOVEMENT_INTERVAL + 1)
                destination = tuple(p + distance * d for p, d in zip(self.current_position, self.away_direction))
                self.steer(destination, now)
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
        self.away_direction = (math.cos(angle), math.sin(angle), 0)
        # Direção preferencial do afastamento; o controle de segurança pode desviá-la.
        distance = constants.EXTERNAL_SPEED * (constants.EXTERNAL_AWAY_DURATION + constants.MOVEMENT_INTERVAL)
        destination = (x + distance * math.cos(angle), y + distance * math.sin(angle), z)
        self.steer(destination, now)

    def target_position(self, time):
        center = self.flight_plan.get_position(time)
        angle = self.target_index * 360 / constants.DRONE_COUNT + constants.ANGULAR_SPEED * time
        return FlightPlan.position_on_circle(center, constants.FORMATION_RADIUS, angle)

    def in_contact(self, now):
        within_range = math.dist(self.current_position, self.target_position(now)) <= constants.EXTERNAL_CONTACT_DISTANCE
        if constants.SIMULATION_MODE == constants.RANDOM:
            return within_range
        return (within_range and math.dist(self.current_position[:2], self.flight_plan.get_position(now)[:2]) >=
                constants.FORMATION_RADIUS + constants.SAFETY_MARGIN)

    def contact_position(self, time):
        if constants.SIMULATION_MODE == constants.RANDOM:
            return self.target_position(time)
        center = self.flight_plan.get_position(time)
        angle = self.target_index * 360 / constants.DRONE_COUNT + constants.ANGULAR_SPEED * time
        return FlightPlan.position_on_circle(
            center, constants.FORMATION_RADIUS + constants.EXTERNAL_CONTACT_OFFSET, angle)

    def find_intercept(self, now):
        """Estima encontro pelo caminho reto com o ponto externo; o desvio pode atrasá-lo."""
        delay = 0.0
        while True:
            target = self.contact_position(now + delay)
            distance = math.dist(self.current_position, target)
            if distance <= constants.EXTERNAL_SPEED * delay:
                return target
            delay += constants.EXTERNAL_INTERCEPT_STEP

    def path_is_safe(self, destination, now):
        """Verifica o próximo passo contra o centro móvel, inclusive entre amostras.

        A folga cobre a amostragem de 0,01 s e uma telemetria de mobilidade atrasada
        em até 0,01 s (intervalo padrão do MobilityHandler deste projeto).
        """
        if constants.SIMULATION_MODE == constants.RANDOM:
            return True
        step = 0.01
        horizon = constants.MOVEMENT_INTERVAL + step
        radius = constants.FORMATION_RADIUS + constants.SAFETY_MARGIN
        buffer = constants.EXTERNAL_SPEED * step + (constants.EXTERNAL_SPEED + constants.CENTER_SPEED) * step / 2
        distance = math.dist(self.current_position, destination)
        for index in range(math.ceil(horizon / step) + 1):
            delay = min(index * step, horizon)
            fraction = min(1, constants.EXTERNAL_SPEED * delay / distance) if distance else 0
            position = tuple(p + fraction * (q - p) for p, q in zip(self.current_position, destination))
            center = self.flight_plan.get_position(now + delay)
            if math.dist(position[:2], center[:2]) < radius + buffer:
                return False
        return True

    def steer(self, destination, now):
        if self.path_is_safe(destination, now):
            self.contour_direction = None
        else:
            center = self.flight_plan.get_position(now)
            angle = math.atan2(self.current_position[1] - center[1], self.current_position[0] - center[0])
            radial = (math.cos(angle), math.sin(angle))
            if self.contour_direction is None:
                cross = radial[0] * (destination[1] - center[1]) - radial[1] * (destination[0] - center[0])
                self.contour_direction = 1 if cross >= 0 else -1
            tangent = (-radial[1] * self.contour_direction, radial[0] * self.contour_direction)
            # Começa tangencialmente; aumenta a componente para fora se o centro
            # estiver avançando sobre o UAV. O último candidato é fuga radial.
            for outward in (0, 0.5, 1, 2, 4, None):
                direction = radial if outward is None else tuple(t + outward * r for t, r in zip(tangent, radial))
                length = math.hypot(*direction)
                distance = constants.EXTERNAL_SPEED * (constants.MOVEMENT_INTERVAL + 1)
                candidate = (
                    self.current_position[0] + distance * direction[0] / length,
                    self.current_position[1] + distance * direction[1] / length,
                    self.current_position[2],
                )
                destination = candidate
                if self.path_is_safe(candidate, now):
                    break
        self.destination = destination
        self.provider.send_mobility_command(GotoCoordsMobilityCommand(*destination))
