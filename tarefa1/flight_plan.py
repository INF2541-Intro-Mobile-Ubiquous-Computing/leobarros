# Plano de vôo do Swarm (trajeto em forma de polígono percorrido ciclicamente 
# pelo centro virtual do core)
class FlightPlan:

    # point: lista de coordenadas
    # segment_duration: tempo gasto para percorrer cada trecho entre os pontos
    def __init__(self, points, segment_duration):
        self.points = points
        self.segment_duration = segment_duration
        # Cada ciclo é percorrido no tempo para percorrer cada trecho * número de pontos
        self.num_segments = len(points)
        self.cycle_duration = self.num_segments * segment_duration

    # Retorna a posição interpolada do centro virtual no instante t
    def get_position(self, t):
        # Converte t (tempo absoluto) para o tempo relativo dentro do ciclo atual
        cycle_time = t % self.cycle_duration
        # Descobre o segmento do trajeto (0: P0->P1, 1: P1->P2, etc)
        segment_index = int(cycle_time // self.segment_duration)
        # Tempo passado desde que começou o ciclo
        time_in_segment = cycle_time % self.segment_duration
        # Fração percorrida no segmento: 0.0 ... 1.0
        progress = time_in_segment / self.segment_duration
        start = self.points[segment_index]
        # O último ponto volta para o primeiro
        end = self.points[(segment_index + 1) % len(self.points)]
        x = start[0] + (end[0] - start[0]) * progress
        y = start[1] + (end[1] - start[1]) * progress
        # Z permanece fixo
        z = 0
        return (x, y, z)