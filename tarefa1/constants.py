import math

# Timers
REPAINT_TIMER = "repaint"
MOVEMENT_TIMER = "movement"

# Intervalos
REPAINT_INTERVAL = 1
MOVEMENT_INTERVAL = 0.1

# Plano de vôo comum aos drones; o instante zero da simulação é o início da missão.
FLIGHT_PLAN_POINTS = ((0, 0, 0), (50, 0, 0), (50, -50, 0), (0, -50, 0))
#FLIGHT_PLAN_POINTS = ((-50, 50, 0), (-50, -50, 0), (50, 50, 0), (50, -50, 0))
CENTER_SPEED = 12.0  # m/s, constante em todos os trechos.
ROTATION_SPEED = 6.0  # m/s tangenciais; negativo inverte a rotação.
FORMATION_RADIUS = 10
ANGULAR_SPEED = math.degrees(ROTATION_SPEED / FORMATION_RADIUS)  # graus/s
DRONE_COUNT = 9
# Velocidade para alcançar os alvos, com 20% de margem sobre a referência máxima.
MOVEMENT_SPEED = 1.2 * (CENTER_SPEED + abs(ROTATION_SPEED))
REAL_TIME = 3.0  # 1: tempo real; 0.5: meia velocidade; 2: dobro da velocidade.

# Cor do nó
DEFAULT_COLOR = (0, 0, 0)

# Tamanho do nó
DEFAULT_SIZE = 1.0
