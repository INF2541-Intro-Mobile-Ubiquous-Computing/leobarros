import math
import constants


class FlightPlan:
    """Geometria do voo e validação dos índices dos satélites."""

    @staticmethod
    def validate_external_index(external_index):
        if type(external_index) is not int or external_index not in constants.EXTERNAL_DIRECTIONS:
            raise ValueError(f'Índice externo desconhecido: {external_index!r}')
        return external_index

    @staticmethod
    def get_position(t):
        """O centro virtual permanece na origem em qualquer instante."""
        return (0, 0, 0)

    @staticmethod
    def position_on_circle(center, radius, angle):
        x_center, y_center, z_center = center
        angle_rad = math.radians(angle)
        return (
            x_center + radius * math.cos(angle_rad),
            y_center + radius * math.sin(angle_rad),
            z_center,
        )
