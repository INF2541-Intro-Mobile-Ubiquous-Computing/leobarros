import math
from bisect import bisect_right
from itertools import accumulate


'''
Plano de vôo do Swarm (trajeto em forma de polígono percorrido ciclicamente 
pelo centro virtual do core)
'''
class FlightPlan:

    '''
    Construtor.
    # points: lista de coordenadas
    # speed: velocidade constante do centro em m/s
    '''
    def __init__(self, points, speed):
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError('A velocidade do centro deve ser positiva e finita.')
        self.points = tuple(tuple(point) for point in points)
        if len(self.points) < 2:
            raise ValueError('O plano deve conter pelo menos dois pontos.')
        if any(len(point) != 3 or not all(math.isfinite(c) for c in point) for point in self.points):
            raise ValueError('Cada ponto deve conter três coordenadas finitas.')
        self.speed = speed
        self.num_segments = len(self.points)
        # Inclui o retorno do último ponto ao primeiro. Trechos maiores duram mais.
        self.segment_durations = tuple(
            math.dist(point, self.points[(index + 1) % self.num_segments]) / speed
            for index, point in enumerate(self.points)
        )
        self.segment_end_times = tuple(accumulate(self.segment_durations))
        self.cycle_duration = self.segment_end_times[-1]
        if self.cycle_duration == 0:
            raise ValueError('O plano deve conter pelo menos dois pontos distintos.')

    '''
    Retorna a posição interpolada do centro virtual no instante t ao longo do plano de vôo
    '''
    def get_position(self, t):
        # Converte t (tempo absoluto) para o tempo relativo dentro do ciclo atual
        cycle_time = t % self.cycle_duration
        # Busca o trecho pelo tempo acumulado; ignora trechos de comprimento zero.
        segment_index = bisect_right(self.segment_end_times, cycle_time)
        segment_start_time = self.segment_end_times[segment_index - 1] if segment_index else 0
        progress = (cycle_time - segment_start_time) / self.segment_durations[segment_index]
        start = self.points[segment_index]
        # O último ponto volta para o primeiro
        end = self.points[(segment_index + 1) % len(self.points)]
        x = start[0] + (end[0] - start[0]) * progress
        y = start[1] + (end[1] - start[1]) * progress
        z = start[2] + (end[2] - start[2]) * progress
        return (x, y, z)

    """
    Retorna a posição no círculo horizontal, com ângulo em graus e Z do centro.
    """
    @staticmethod
    def position_on_circle(center, radius, angle):
        x_center, y_center, z_center = center
        angle_rad = math.radians(angle)
        return (
            x_center + radius * math.cos(angle_rad),
            y_center + radius * math.sin(angle_rad),
            z_center,
        )
