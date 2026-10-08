from gradysim.protocol.interface import IProtocol
from gradysim.simulator.extension.visualization_controller import VisualizationController
import constants

'''
Nó visível no Grid
'''
class VisibleNodeProtocol (IProtocol):

    '''
    Inicialização do nó
    '''
    def initialize(self):
        self.show_in_grid()
        self.schedule_repaint_timer()

    '''
    Recebimento de mensagens
    '''
    def handle_packet(self, message):
        pass

    '''
    Recebimento de telemetria
    '''    
    def handle_telemetry(self, telemetry):
        pass

    '''
    Tick dos relógios
    '''
    def handle_timer(self, timer):
        if timer == constants.REPAINT_TIMER:
            self.repaint()

    '''
    Finalização do objeto
    '''
    def finish(self):
        pass

    '''
    Garante que o nó possa ser exibido no Grid
    '''
    def show_in_grid(self):
        self.visualization = VisualizationController(self)

    '''
    Programa um timer para repaint do nó
    '''
    def schedule_repaint_timer(self):
        self.provider.schedule_timer(
            constants.REPAINT_TIMER,
            self.provider.current_time() + constants.REPAINT_INTERVAL
        )

    '''
    Repinta o nó, definindo sua cor e tamanho
    '''
    def repaint(self):
        self.currentColor = constants.DEFAULT_COLOR
        self.visualization.resize_nodes(constants.DEFAULT_SIZE)
        self.visualization.paint_node(self.provider.get_id(), self.currentColor)
        self.schedule_repaint_timer()    