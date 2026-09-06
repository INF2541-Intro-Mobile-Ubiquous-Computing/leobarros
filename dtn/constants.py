# Mensagens
NO_MESSAGE_RECEIVED = 0
QUESTION_RECEIVED = 1
ANSWER_RECEIVED = 2

# Intervalos
SEND_QUESTION_INTERVAL = 5 # de envio de pergunta
MOBILITY_INTERVAL = 2 # de movimento do nó
REPAINT_INTERVAL = 1 # de pintura do nó

# Cor do nó
UAV_COLOR = (60, 60, 60)
QUESTION_COLOR = (255, 0, 0)
ANSWER_COLOR = (0, 0, 255)
TOWER_COLOR = (255, 100, 100)

# Tamanho do nó
DEFAULT_SIZE = 1.0

NODE_LEVELS = {
    0: 0,
    1: 1,
    2: 1,
    3: 2,
    4: 2,
    5: 3,
    6: 3,
}
# Tempo máximo de retenção de uma mensagem DTN, em segundos simulados.
MESSAGE_TTL = 60
