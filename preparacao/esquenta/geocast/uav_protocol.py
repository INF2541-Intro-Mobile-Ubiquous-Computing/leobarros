from node_protocol import NodeProtocol
import constants

class UAVProtocol (NodeProtocol):

    def initialize(self):
        super().initialize()
        self.color = constants.UAV_COLOR
        self.scheduleMobilityTimer()

    def deliverMessage(self, packet):
        if packet["type"] == "PERGUNTA":
            self.sendMessage("RESPOSTA", self.answerText(), packet["reply_region"])

    def answerText(self):
        return "E eu sei lá, ué"

    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == "mobility":
            self.move()

    def scheduleMobilityTimer(self):
        self.provider.schedule_timer("mobility", self.provider.current_time() + constants.MOBILITY_INTERVAL)

    def move(self):
        pass
