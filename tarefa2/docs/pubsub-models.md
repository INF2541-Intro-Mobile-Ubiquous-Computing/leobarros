# Modelos e envelopes Pub/Sub

[models.py](../src/pubsub/models.py) define contratos de dados sem dependência do simulador, da configuração, do roteamento ou da mobilidade. Não cria estado global compartilhado entre UAVs.

`Publication` contém `message_id`, `topic`, `origin_id`, `origin_region`, `created_at` e `payload`. O ID da publicação é fornecido pelo chamador; o módulo não gera IDs nem verifica sua unicidade. `origin_id` é o ID do nó de origem e `created_at` representa tempo simulado em segundos. O payload deve usar valores JSON: objetos com chaves string, listas, strings, números finitos, booleanos ou null.

`Subscription` contém `subscriber_id`, `topic` e `accepted_regions`. As regiões válidas são `N`, `S`, `E`, `W` e `C`, representadas pelo enum `Region`. A assinatura copia as regiões para um `frozenset`; duplicatas são eliminadas. O conjunto vazio é representável, sem regiões aceitas. Não há execução de filtros nesta etapa.

Todos os envelopes têm `msg_type="pubsub"`, `operation` e `sender_id`. Este último é o emissor da operação de aplicação, não o próximo salto de roteamento. É independente do originador da publicação e do assinante: um PSPeer pode entregar uma publicação de outro UAV. As operações são valores do enum `Operation`.

| Classe | Operação | Campos específicos |
| --- | --- | --- |
| `SubscribeEnvelope` | `SUBSCRIBE` | `subscription: Subscription` |
| `PublishEnvelope` | `PUBLISH` | `publication: Publication` |
| `FetchEnvelope` | `FETCH` | `subscriber_id`, `topic` |
| `DeliverEnvelope` | `DELIVER` | `subscriber_id`, `publications: tuple[Publication, ...]` |
| `SyncEnvelope` | `SYNC` | `subscriptions: tuple[Subscription, ...]` |

`FETCH` ainda não contém cursor ou lista de IDs lidos; a política de leitura será implementada separadamente. `DELIVER` aceita um lote vazio ou várias publicações. `SYNC` descreve alterações de assinaturas, conforme a especificação; não define transporte, replicação de publicações, versões, remoções ou resolução de conflitos. Os lotes recebidos pelos construtores são copiados para tuplas.

## Serialização

```python
from src.pubsub.models import (
    Region, Subscription, SubscribeEnvelope, envelope_from_json,
)

subscription = Subscription(
    subscriber_id=15,
    topic="T1",
    accepted_regions={Region.N, Region.C},
)
envelope = SubscribeEnvelope(sender_id=15, subscription=subscription)
wire_message = envelope.to_json()
restored = envelope_from_json(wire_message)
assert restored == envelope
```

JSON produzido:

```json
{"msg_type":"pubsub","operation":"SUBSCRIBE","sender_id":15,"subscription":{"accepted_regions":["C","N"],"subscriber_id":15,"topic":"T1"}}
```

`to_json()` ordena as chaves e as regiões para evitar variações causadas pela ordem de conjuntos. `to_dict()` retorna contêineres próprios compatíveis com JSON. `envelope_from_json()` e `envelope_from_dict()` restauram a classe específica e seus modelos aninhados, sem modificar o dicionário de entrada. Regiões inválidas, operações desconhecidas, campos ausentes ou extras no formato e JSON inválido são rejeitados. Valores não serializáveis e NaN/Infinity falham na serialização.

Os tipos dos campos são anotações Python, não um validador completo de valores em tempo de execução. Por exemplo, pertencimento do tópico à configuração, validade dos IDs, autorização, unicidade e limites de tempo ainda não são verificados. Os modelos usam `dataclass(frozen=True)`, mas a imutabilidade é superficial: um payload que contenha dicionários/listas continua mutável na instância. A conversão para o envelope serializado produz dados separados.

## Escopo e testes

Não há handlers de operação, agendamento de eventos, armazenamento de tópicos, transporte ou alteração do SwCore. Os parâmetros ajustáveis continuam em `utils/common/config.py`; nomes de operações e regiões são partes fixas do contrato.

[test_pubsub_models.py](../tests/test_pubsub_models.py) acrescenta nove testes de serialização, filtros, regiões, lotes vazios, isolamento de contêineres e erros. A suíte completa passou com **30 testes**:

```powershell
../.venv/Scripts/python.exe -B -m unittest discover -s tests -v
```
