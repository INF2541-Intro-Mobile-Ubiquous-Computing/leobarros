from visible_node_protocol import VisibleNodeProtocol
import constants, logging

# Nó que pode se mover
class MovableNodeProtocol (VisibleNodeProtocol):

    # Inicialização do nó
    def initialize(self):
        super().initialize()
        self.schedule_movement_timer()

    # Tick dos relógios
    def handle_timer(self, timer):
        super().handle_timer(timer)
        if timer == constants.MOVEMENT_TIMER:
            self.move()
            self.schedule_movement_timer()

    # Programa um timer para movimentação
    def schedule_movement_timer(self):
        self.provider.schedule_timer(constants.MOVEMENT_TIMER, 
            self.provider.current_time() + constants.MOVEMENT_INTERVAL)

    def move(self):
        pass
    