# Histórico de publicações por tópico

[TopicStore](../src/pubsub/topic_store.py) mantém publicações em memória, com estado exclusivo de cada instância. Não depende do simulador, do SwCore nem de estruturas globais compartilhadas.

```python
from src.pubsub.models import Publication, Region
from src.pubsub.topic_store import TopicStore

store = TopicStore()
publication = Publication("uav12:1", "T1", 12, Region.N, 2.5, {"value": 42})
assert store.add_publication(publication) is True
assert store.add_publication(publication) is False
assert store.get_history("T1") == (publication,)
```

- `add_publication(publication) -> bool`: adiciona uma publicação inédita e retorna `True`; retorna `False` se o `message_id` já existir em qualquer tópico da mesma instância. A primeira publicação prevalece, sem substituição, mesclagem ou mudança de posição, mesmo diante de conteúdo ou tópico divergente.
- `get_history(topic) -> tuple[Publication, ...]`: devolve uma cópia do histórico na ordem em que as publicações foram adicionadas com sucesso. Um tópico desconhecido ou vazio retorna `()`. A consulta não consome mensagens.

A ordem é de chegada ao store, não de criação: se publicações com `created_at=30`, `5` e `30` forem adicionadas nessa sequência, ela será preservada. Todos os campos de `Publication`, incluindo `created_at`, são mantidos. Não é introduzido um relógio ou timestamp de chegada; a posição no histórico registra a sequência de inserção.

Publicações são copiadas profundamente ao inserir e consultar, pois seus payloads podem conter listas/dicionários mutáveis. Uma consulta é um snapshot: novas inserções e alterações no payload retornado não modificam snapshots anteriores nem o histórico interno. A consulta custa uma cópia do histórico do tópico; a verificação de duplicação usa um conjunto de IDs.

O store não valida tópicos contra `PUBSUB_TOPICS`, não limita retenção, não persiste em disco e não controla filtros, assinaturas ou mensagens lidas. Também não sincroniza instâncias nem é integrado aos protocolos nesta etapa. Cada futura instância de protocolo poderá possuir seu próprio store.

[test_topic_store.py](../tests/test_topic_store.py) verifica inserção, ordem de chegada, preservação de `created_at`, separação por tópico, duplicatas idênticas/conflitantes, isolamento de payloads, snapshots e independência entre instâncias.
