import math
from types import MappingProxyType


class FlightPlan:
    """Formação com centro fixo na origem e associação dos alvos externos."""

    def __init__(self, external_targets=None, core_count=None):
        targets = dict(external_targets or {})
        if targets and (type(core_count) is not int or core_count <= 0):
            raise ValueError('Informe a quantidade de nós do core para validar os alvos.')
        for external, target in targets.items():
            if type(external) is not int or external < 0:
                raise ValueError('Índice externo deve ser inteiro não negativo.')
            if type(target) is not int or not 0 <= target < core_count:
                raise ValueError('Índice do alvo externo fora do core.')
        self.external_targets = MappingProxyType(targets)

    def get_core_target(self, external_index):
        """Consulta o ponto de encontro do externo; rejeita índices desconhecidos."""
        if type(external_index) is not int or external_index not in self.external_targets:
            raise ValueError(f'Índice externo desconhecido: {external_index!r}')
        return self.external_targets[external_index]

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
