import math

# Nível mínimo: DEBUG, INFO, WARNING, ERROR ou CRITICAL.
LOG_LEVEL = 'WARNING'

TOPOLOGY = 'TOPOLOGY'
RANDOM = 'RANDOM'
SIMULATION_MODE = TOPOLOGY
EXECUTION_CYCLES = 1 # Número de ciclos de execução do plano de vôo
RANDOM_DIRECTION_INTERVAL = 1.0  # novo rumo a cada segundo ou ao atingir a borda
RANDOM_SPEED = 6.0  # m/s em relação ao centro móvel
RANDOM_MOVEMENT_INTERVAL = 0.01  # deve coincidir com a atualização de mobilidade
DISCOVERY_RESPONSE_TIMEOUT = 1.0
DISCOVERY_PROBE_TIMEOUT = 0.25
DISCOVERY_TIMER = 'discovery'

# Timers
REPAINT_TIMER = "repaint"
RESTORE_COLOR_TIMER = "restore_color"
MOVEMENT_TIMER = "movement"
CONTACT_TIMER = "contact"

# Intervalos
REPAINT_INTERVAL = 1
MESSAGE_COLOR_DURATION = 1.0
MOVEMENT_INTERVAL = 0.1

# Plano de vôo comum aos drones; o instante zero da simulação é o início da missão.
FLIGHT_PLAN_POINTS = ((0, 0, 0), (50, 0, 0), (50, -50, 0), (0, -50, 0))
#FLIGHT_PLAN_POINTS = ((-50, 50, 0), (-50, -50, 0), (50, 50, 0), (50, -50, 0))
CENTER_SPEED = 12.0  # m/s, constante em todos os trechos.
ROTATION_SPEED = 6.0  # m/s tangenciais; negativo inverte a rotação.
FORMATION_RADIUS = 10
ANGULAR_SPEED = math.degrees(ROTATION_SPEED / FORMATION_RADIUS)  # graus/s
DRONE_COUNT = 9
# Índices próprios dos externos, independentes dos IDs globais do simulador.
EXTERNAL_CORE_TARGETS = {0: 0, 1: 2, 2: 4, 3: 6}
EXTERNAL_DESTINATIONS = {0: 1, 1: 0, 2: 3, 3: 2}
# Velocidade para alcançar os alvos, com 20% de margem sobre a referência máxima.
MOVEMENT_SPEED = 1.2 * (CENTER_SPEED + abs(ROTATION_SPEED))
REAL_TIME = 3.0  # 1: tempo real; 0.5: meia velocidade; 2: dobro da velocidade.

# UAV externo: movimento e contato com a posição prevista de um membro do core.
EXTERNAL_TARGET_INDEX = 0
EXTERNAL_SPEED = 24.0  # m/s
EXTERNAL_AWAY_DURATION = 5.0  # segundos simulados
EXTERNAL_CONTACT_TIMEOUT = 2.0  # tempo máximo da troca antes de se afastar
EXTERNAL_CONTACT_RETRY_INTERVAL = 0.25  # repete a presença se houver perda
EXTERNAL_CONTACT_DISTANCE = 5.0  # metros
# Corda entre vizinhos + folga para o acompanhamento discreto da formação.
RADIO_RANGE = max(EXTERNAL_CONTACT_DISTANCE,
                  2 * FORMATION_RADIUS * math.sin(math.pi / DRONE_COUNT)) + 3.0
EXTERNAL_INTERCEPT_STEP = 0.05  # resolução temporal da busca, em segundos
SAFETY_MARGIN = 2.0  # área de exclusão: raio da formação + margem
EXTERNAL_CONTACT_OFFSET = 3.0  # ponto de contato radialmente para fora do alvo

# Cor do nó
DEFAULT_COLOR = (0, 0, 0)
PAIR_COLORS = {
    0: (0, 114, 178),    # Azul
    2: (230, 159, 0),    # Laranja
    4: (0, 158, 115),    # Verde
    6: (204, 121, 167),  # Magenta
}

# Tamanho do nó
DEFAULT_SIZE = 1.0
