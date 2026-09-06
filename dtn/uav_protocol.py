from node_protocol import NodeProtocol
import constants, logging
from typing import Optional
from gradysim.protocol.position import Position
from gradysim.protocol.messages.communication import CommunicationCommand, CommunicationCommandType
from collections import deque

class UAVProtocol (NodeProtocol):

    # Inicialização
    def initialize(self):
        super().initialize()
        self.color = constants.UAV_COLOR # Cor default do drone
        self.current_position: Optional[Position] = None
        self.level = constants.NODE_LEVELS[self.provider.get_id()]
        self.communicationCommands = deque()
        self.scheduleMobilityTimer()

    # Recebimento de mensagens
    def handle_packet(self, message):
        senderLevel = self.getSenderLevel(message)
        if senderLevel is None:
            logging.error(f"Mensagem sem nível: {message}")
            return
        isQuestion = "[PERGUNTA]" in message
        isAnswer = "[RESPOSTA]" in message
        if isQuestion and senderLevel >= self.level: # Perguntas somente avançam
            return
        if isAnswer and senderLevel <= self.level: # Respostas somente retornam
            return
        if not isQuestion and not isAnswer:
            logging.error(f"Mensagem não é pergunta nem resposta: {message}")
            return
        if not self.acceptMessage(message):
            return
        self.received += 1
        if isQuestion:
            self.messageReceivedType = constants.QUESTION_RECEIVED
        elif isAnswer:
            self.messageReceivedType = constants.ANSWER_RECEIVED
        forwardedMessage = f"[{self.level}]{message}"
        self.scheduleForwardMessage(forwardedMessage)

    def scheduleForwardMessage(self, message):
        command = CommunicationCommand(CommunicationCommandType.BROADCAST, message)
        self.communicationCommands.append(command)
    
    def scheduleAnswer(self):
        message = (f"[{self.level}][RESPOSTA] E eu sei lá, ué")
        self.scheduleForwardMessage(self.createMessage(message))

   # Recebimento de telemetria
    def handle_telemetry(self, telemetry):
        self.current_position = telemetry.current_position

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.moveAndSendMessage()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer("mobility", self.provider.current_time() + constants.MOBILITY_INTERVAL)

    def moveAndSendMessage(self):
        self.move()
        for _ in range(len(self.communicationCommands)):
            command = self.communicationCommands.popleft()
            if self.isMessageValid(command.message):
                self.provider.send_communication_command(command)
                self.sent += 1
                self.communicationCommands.append(command) # Guarda para o próximo contato.

    def move(self):
        pass

    def getSenderLevel(self, message):
        if not message.startswith("["):
            return None
        closingBracket = message.find("]")
        if closingBracket == -1:
            return None
        try:
            return int(message[1:closingBracket])
        except ValueError:
            return None