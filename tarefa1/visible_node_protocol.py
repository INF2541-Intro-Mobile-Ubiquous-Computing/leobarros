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
        self.temporary_color = None
        self.temporary_color_until = 0
        self.show_in_grid()
        self.repaint()

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
        elif timer == constants.RESTORE_COLOR_TIMER:
            # Um timer antigo não deve encerrar o destaque de uma nova mensagem.
            if self.provider.current_time() >= self.temporary_color_until:
                self.temporary_color = None
                self.paint_current_color()

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
        self.visualization.resize_nodes(constants.DEFAULT_SIZE)
        self.paint_current_color()
        self.schedule_repaint_timer()

    def show_message_color(self, color):
        """Destaca o recebimento por um segundo, preservando a cor original."""
        self.temporary_color = tuple(color)
        self.temporary_color_until = self.provider.current_time() + constants.MESSAGE_COLOR_DURATION
        self.paint_current_color()
        self.provider.schedule_timer(constants.RESTORE_COLOR_TIMER, self.temporary_color_until)

    def paint_current_color(self):
        self.currentColor = (self.temporary_color if self.temporary_color is not None
                             else getattr(self, 'color', constants.DEFAULT_COLOR))
        self.visualization.paint_node(self.provider.get_id(), self.currentColor)
