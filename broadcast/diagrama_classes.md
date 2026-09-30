# Diagrama de classes de broadcast

O diagrama mostra as seis classes definidas nesta pasta e sua herança. `IProtocol` pertence à biblioteca GraDyS. Cada classe lista seus métodos declarados; os demais são herdados. Os tipos dos atributos são indicados conforme as anotações ou o uso no código.

```mermaid
classDiagram
    direction TB

    class IProtocol {
        <<external>>
    }

    class NodeProtocol {
        +int sent
        +int received
        +int messageReceivedType
        +tuple defaultColor
        +tuple currentColor
        +VisualizationController visualization
        +initialize()
        +handle_packet(message)
        +handle_telemetry(telemetry)
        +handle_timer(timer)
        +finish()
        +scheduleAppearanceTimer()
        +setColorAndSize()
    }

    class TowerProtocol {
        +str lastResponse
        +initialize()
        +handle_packet(message)
        +handle_timer(timer)
        +sendQuestion()
        +scheduleSendQuestionTimer()
        +finish()
    }

    class UAVProtocol {
        +tuple color
        +Position current_position
        +int level
        +deque communicationCommands
        +initialize()
        +handle_packet(message)
        +scheduleForwardMessage(message)
        +handle_telemetry(telemetry)
        +handle_timer(timer)
        +scheduleMobilityTimer()
        +moveAndSendMessage()
        +move()
        +getSenderLevel(message)
    }

    class HorizontalUAVProtocol {
        +move()
    }

    class VerticalUAVProtocol {
        +move()
    }

    class FinalUAVProtocol {
        +handle_packet(message)
    }

    IProtocol <|-- NodeProtocol
    NodeProtocol <|-- TowerProtocol
    NodeProtocol <|-- UAVProtocol
    UAVProtocol <|-- HorizontalUAVProtocol
    UAVProtocol <|-- VerticalUAVProtocol
    HorizontalUAVProtocol <|-- FinalUAVProtocol
```

A seta com triângulo aponta para a classe base. `lastResponse` e `current_position` começam com `None`.

- **NodeProtocol**: mantém contadores e controla a aparência dos nós.
- **TowerProtocol**: envia perguntas periodicamente e recebe respostas do nível 1.
- **UAVProtocol**: encaminha perguntas para níveis superiores e respostas para níveis inferiores, enviando as mensagens enfileiradas após o movimento.
- **HorizontalUAVProtocol**: implementa movimento no eixo X.
- **VerticalUAVProtocol**: implementa movimento no eixo Y.
- **FinalUAVProtocol**: herda o movimento horizontal e responde imediatamente às perguntas recebidas de níveis inferiores.

`main.py` monta a simulação e `constants.py` define as constantes; nenhum deles declara classes. `ANSWERS`, em `final_uav_protocol.py`, é uma constante do módulo.
