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
        +set seenMessageIds
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
        +getMessageId(message)
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
        +initialize()
        +handle_packet(message)
        +handle_telemetry(telemetry)
        +handle_timer(timer)
        +scheduleMobilityTimer()
        +move()
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

- **NodeProtocol**: mantém contadores, o conjunto de IDs já vistos e controla a aparência dos nós.
- **TowerProtocol**: envia perguntas periodicamente e recebe respostas, ignorando IDs repetidos.
- **UAVProtocol**: encaminha imediatamente cada pergunta ou resposta uma única vez por ID, sem armazenar mensagens para envio posterior.
- **HorizontalUAVProtocol**: implementa movimento no eixo X.
- **VerticalUAVProtocol**: implementa movimento no eixo Y.
- **FinalUAVProtocol**: herda o movimento horizontal e responde imediatamente uma única vez a cada ID de pergunta.

`main.py` monta a simulação e `constants.py` define as constantes; nenhum deles declara classes. `ANSWERS`, em `final_uav_protocol.py`, é uma constante do módulo.
