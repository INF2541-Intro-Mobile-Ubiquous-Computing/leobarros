# Continuidade do projeto Tarefa 2

Atualizado em 15/11/2026, após implementar a etapa 21. Leia este arquivo primeiro na nova conversa; depois, apenas os trechos de código relevantes à etapa autorizada. Este resumo não autoriza iniciar outra etapa automaticamente.

## Regras do usuário e modo econômico

- Trabalhar exclusivamente em `tarefa2`. Nunca modificar `routing-ricardo` ou a dependência instalada.
- Executar **uma etapa por vez**. Ao concluir, parar para o usuário inspecionar, revisar e commitar. Só avançar quando solicitado. Não fazer commits, staging ou push automaticamente.
- Preservar mobilidade, SwCore e comunicação original dos satélites. Não implementar funcionalidades de etapas futuras.
- Antes de editar, examinar classes/funções relevantes e apresentar um plano breve. Perguntar somente quando uma decisão importante estiver bloqueada.
- Manter Pub/Sub separado do roteamento/mobilidade, com estado próprio de cada instância. Comunicação entre nós somente por mensagens simuladas, nunca por registradores globais compartilhados.
- Centralizar parâmetros ajustáveis em `utils/common/config.py`. A instrução original mencionava `constants.ts`, mas a base é Python e a configuração foi mantida em `config.py` ao longo das etapas.
- Manter sementes configuráveis e determinismo quando possível.
- Respostas curtas, buscas/leituras direcionadas, sem reimprimir arquivos completos já conhecidos, sem documentação adicional salvo necessidade. Não reabrir todo o roteiro a cada etapa; usar a tabela abaixo.
- Testes pertinentes à alteração. Simulação completa quando houver integração de protocolos/comunicação; não repetir execuções sem justificativa. Reportar somente resultado, arquivos, comportamento e limitações importantes.
- Ao concluir uma etapa, informar contagem de testes, limitações e mensagem de commit sugerida. Não iniciar a próxima na mesma entrega.
- Não usar subagentes sem solicitação explícita. Não pesquisar na web para questões respondidas pelo código local.

## Ambiente e fontes

- Workspace: `D:\doutorado\endler\getting-started`; shell PowerShell.
- Projeto: `tarefa2`; original preservado: `routing-ricardo`, no mesmo diretório raiz.
- Ambas as pastas pertencem ao Git raiz, remoto `leobarros`. Não são repositórios Git separados. Não foi configurado remoto para o repositório original do Ricardo.
- Python disponível: `../.venv/Scripts/python.exe` a partir de `tarefa2`; GrADyS-SIM 0.8.0. `requirements.txt` declara `gradysim` sem versão fixada.
- Especificação: `tarefa2/especificacao_extraida.txt` e `especificacao_original.docx`.
- Roteiro: `C:\Users\lbarros\Downloads\Roteiro de Implementação - Tarefa 2.pdf`, 26 etapas. O PDF fornecido marca 01–06 como OK, mas a conversa avançou até 12.
- `docs/architecture.md` descreve a base inicial e suas limitações; partes são históricas. Código atual e este resumo prevalecem para o estado implementado.
- `CONTEXTO.md` e `PREPARACAO.md` são registros anteriores; não confundir suas descrições iniciais com o estado atual.
- O roteiro contém propostas arquiteturais e instruções futuras; sua existência não autoriza executar tudo de uma vez.
- Para extrair trechos do PDF, `pypdf` foi instalado somente em `tarefa2/.cache/pdf-reader`. Se necessário, acrescentar esse caminho ao `sys.path`, usar `sys.stdout.reconfigure(encoding='utf-8')` e normalizar espaços de `page.extract_text()`: o PDF extrai quase uma palavra por linha. Não instalar novamente.

## Estado atual e revisão pendente

**Etapas 01–21 implementadas e testadas. Próxima: 22, somente após solicitação do usuário.** Os PSPeers sincronizam assinaturas, replicam publicações e enviam DELIVER individual aos assinantes elegíveis. Satélites conectados têm cliente Pub/Sub opt-in. Coletas reais de sensores agora geram publicações nos satélites; o core também gera publicações aleatórias com região C; core e satélites agora geram assinaturas dinâmicas reproduzíveis.

Na entrada da etapa 21, `git status --short tarefa2` estava limpo. As mudanças desta etapa ficam para revisão e commit do usuário; nenhum comando de staging ou commit foi executado pelo agente.

| Etapas concluídas | Resultado |
| --- | --- |
| 01–03 | Cópia limpa, baseline SwCore e mapeamento da arquitetura |
| 04 | `--pubsub` força `star` + `swcore`, mesmo diante de opções conflitantes; parâmetros centralizados |
| 05–06 | Modelos/envelopes e `TopicStore` |
| 07–08 | `SubscriptionStore` e `ConsumptionStore` |
| 09–10 | `PSPeerService`, regressões e suíte local independente do simulador |
| 11 | Três rims com serviço PSPeer próprio, identificação INFO e cor verde |
| 12 | Transporte core–core opt-in, direto ou via hub, com rádio simulado e callback de recepção |
| 13 | Adaptador cliente/PSPeer e respostas FETCH pelo rádio |
| 14 | SYNC de assinaturas por broadcast único, versões idempotentes e testes de perdas |
| 15 | REPLICATE de publicações por broadcast único, deduplicação e consulta em B/C após publicação em A |
| 16 | DELIVER individual por peer responsável, deduplicação de push e cliente de satélite durante contato |

## Contratos implementados

Arquivos em `src/pubsub/`:

- `models.py`: dataclasses `Publication(message_id, topic, origin_id, origin_region, created_at, payload)` e `Subscription(subscriber_id, topic, accepted_regions)`. Regiões N/S/E/W/C. Filtro normalizado para `frozenset`. Dataclasses frozen, mas payload é mutável; não presumir imutabilidade profunda.
- Envelopes: `SubscribeEnvelope(sender_id, subscription)`, `PublishEnvelope(sender_id, publication)`, `FetchEnvelope(sender_id, subscriber_id, topic)`, `DeliverEnvelope(sender_id, subscriber_id, publications)` e `SyncEnvelope(sender_id, subscriptions)`. Todos usam `msg_type='pubsub'` e operação explícita. `to_json/to_dict` e `envelope_from_json/envelope_from_dict`; serialização determinística, regiões ordenadas.
- `SyncEnvelope` transporta **somente assinaturas** e `version` (inteiro não negativo). Versão zero preserva leitura de dados antigos, mas não é aplicada. Atualizações usam contador Lamport positivo e ID do emissor para desempate, por chave `(subscriber_id, topic)`.
- `topic_store.py`: `TopicStore.add_publication()` retorna True se inseriu, False se ID já existe em qualquer tópico da mesma instância; primeira versão prevalece. `get_history(topic)` devolve snapshot em tupla, ordem de chegada, mantendo `created_at`; cópias profundas na entrada/consulta.
- `subscription_store.py`: `matches(subscription, publication)` exige tópico igual e região aceita. `add_subscription()` insere/substitui filtro por `(subscriber_id, topic)`, retornando se mudou. `get_subscription()` e `get_matching_subscriptions()`.
- `consumption_store.py`: recebe stores locais no construtor; `get_unread(subscriber_id, topic)` retorna histórico elegível não consumido. Consultas não alteram estado. `mark_consumed(subscriber_id, topic, message_id)` registra confirmação explícita; False para assinatura/ID desconhecido ou repetição. Não confere filtro atual, permitindo confirmação tardia após troca do filtro. O chamador é responsável por confirmar recebimento real. Não há ACK de rede.
- `pspeer_service.py`: cada serviço cria seus próprios stores; API local `subscribe`, `publish`, `fetch`, `mark_consumed`. `subscribe_local(subscription, peer_id)` produz delta versionado somente se houve mudança; `apply_sync()` aplica versões novas sem repropagar nem limpar consumo. O adaptador usa essas APIs para sincronização. Chamadas diretas à API local `subscribe()` não emitem SYNC.
- `pspeer_mixin.py`: `PSPeerMixin.initialize()` chama `super`, cria `self.pspeer_service` e registra INFO com ID e slot. Atributos `is_pspeer=True`, `pspeer_slot`.
- `transport.py`: `PubSubTransportMixin` sobre `SWCoreMixin`, ativo somente no core com `--pubsub`. `send_pubsub(destination, envelope) -> bool`; `handle_pubsub(envelope, source_id)` é hook de recepção que atualmente só registra DEBUG.

### Transporte e composição

`src/uav.py` monta o roteamento opt-in como `PubSubAdapterMixin, PubSubTransportMixin, SWCoreMixin`. Nas fábricas, vêm antes deles `NeighborMixin` e `CoreDockMixin`; o protocolo rim inclui `PSPeerMixin` quando selecionado. O adaptador sobrescreve o hook `handle_pubsub()` e usa somente o serviço local do nó; a resolução do hook nas fábricas é testada.

O transporte core usa os beacons/fresh_neighbors existentes e `_send()` do SwCore. Destino vizinho recebe diretamente; caso contrário, vai ao hub conhecido. O hub encaminha para o destino vizinho. Sem próximo salto, retorna False; um intermediário sem rota descarta. Não há discovery extra, retry, buffering Pub/Sub core–core ou confirmação. True significa envio ao próximo salto, **não entrega**. Destino próprio despacha localmente, sem unicast a si mesmo.

O envelope externo `pubsub_core` contém `transport_id` por origem/contador, `source_id`, destino, saltos, próximo salto e payload da aplicação. Deduplicação por instância e limite de saltos. O emissor de aplicação permanece no envelope interno. Além do core em estrela, desde a etapa 16 consulta `_rt` do SwCore para alcançar satélites conectados (`direct`/`hop`); indisponibilidade conhecida retorna False. DELIVER para satélites conhecidos sem rota utilizável é retido em entradas isoladas no buffer SwCore. O caminho satélite–satélite original foi preservado.

## Parâmetros e logs

Em `utils/common/config.py`: `PUBSUB_ENABLED=False`, tópicos T1/T2, `PSPEER_SLOTS=(0,3,6)` (índices de rims, nunca IDs dinâmicos), `PSPEER_COLOR=(0,200,100)`, `PUBSUB_SEED=2056`, intervalos de publicação/assinatura de 5 s e `PUBSUB_TRANSPORT_MAX_HOPS=8`. Semente e intervalos já geram publicações do core e assinaturas dinâmicas de core/satélites. Validam-se três slots distintos, inteiros e dentro da borda.

Por pedido do usuário, todos os logs detalhados preexistentes da aplicação foram movidos para DEBUG. `LOG_LEVEL='INFO'` mantém início/fim/tempo total e identificação dos três PSPeers. Novos logs INFO de aplicação poderão ser acrescentados conforme as etapas pedirem, sem restaurar o ruído antigo.

`utils/common/logging_config.py` reaplica nível e filtros antes/depois de `builder.build()`. GrADyS-SIM redefine nível e adiciona handler; a configuração local conserva somente o mais recente handler de console do simulador, eliminando duplicação `INFO:root:`/`INFO`. Preserva handlers de arquivo/customizados. Logs informativos internos da biblioteca viram DEBUG, exceto início/fim/tempo total; erros/avisos da biblioteca continuam visíveis. Não editar a dependência.

## O que falta no roteiro

| Etapa | Escopo e validação principal |
| --- | --- |
| 13 — concluída | Comunicar UAVs e PSPeers: processar SUBSCRIBE/PUBLISH/FETCH pelo adaptador. Cliente conhece apenas o PSPeer escolhido. Testar um UAV assinando, publicando e consultando através do rádio, com logs comprovando o caminho. Não antecipar sincronização. |
| 14 — concluída | SYNC após alteração local, broadcast de alcance próprio, versões idempotentes, três réplicas e perdas testadas; sem repropagar, ACK ou retransmitir. |
| 15 — concluída | Política confirmada pelo usuário: armazenar e emitir um broadcast REPLICATE para cada publicação nova; receptores deduplicam e não repropagam. Sem ACK/retry, admitindo históricos divergentes por perdas. |
| 16 — concluída | DELIVER individual aos assinantes elegíveis, responsabilidade pelo peer da versão da assinatura, cliente de satélite conectado, deduplicação de push. TF01/02/03 testados. |
| 17 — concluída | Reconexão e consumo incremental: FETCH ao conectar, reutilização de buffers SwCore, distinguir pendente/enviado/recebido. TF06 com IDs exatos e reconexões repetidas. Resolver confirmação/controle distribuído de consumo e troca de peer. |
| 18 — concluída | Identificação única/estável de sensores; par→T2, ímpar→T1, preservando coleta original. Testar/logar ambas as paridades. |
| 19 — concluída | Converter coleta dos satélites em publicações reais por tópico/paridade e região N/S/E/W; armazenar durante afastamento e transmitir no contato. |
| 20 — concluída | Timers de publicações aleatórias do core em T1/T2, região C, semente reproduzível; entrega conforme filtro. TF04. |
| 21 — concluída | Assinaturas dinâmicas de core/satélites, tópico e subconjunto de regiões por semente; satélites enviam no contato; permitir ambos os tópicos. Histórico elegível e TF05. |
| **22 — próxima** | Cenário integrado com três peers, eventos dinâmicos, filtros, sincronização, histórico e reconexão. Logs estruturados. Executar ciclo relevante de todos os satélites. |
| 23 | Automatizar TF01–TF06 usando comunicação real simulada, não apenas chamadas locais. Executar isolados/juntos; TF06 verifica IDs, não só contagem. |
| 24 | Métricas por (publicação, assinante): entregas, latência, saltos; separar controle, sincronização, retransmissões SwCore e duplicatas. Validar denominadores em cenários pequenos. |
| 25 | Runner reproduzível com semente/duração/parâmetros e exportação CSV/JSON; repetir sementes e comparar resultados. Métricas definitivas dependem do professor. |
| 26 | README final, instalação/execução/testes/parâmetros/limitações/métricas, diagrama e responsabilidades; validar ambiente limpo e autonomia da pasta tarefa2. |

Marcos: M2 (lógica local) concluído na 10; M3 assinaturas sincronizadas concluído na 14; M4 rede/reconexão concluído na 17; M5 integração na 22; M6 entrega na 26.

## Questões importantes ainda não resolvidas

- Alcance resolvido: `radio.py` usa `PUBSUB_SYNC_RANGE=CORE_DIAMETER+1.0` (59,5 m) para `SyncBroadcastCommand` e, desde a etapa 15, `ReplicateBroadcastCommand`. Rádio comum continua em 30 m. Preserva perda/atraso do meio; não altera dependência, não usa flooding nem registro global de aplicação. Nós fora do core podem ouvir e ignoram esses tipos de pacote.
- Confirmação/consumo resolvido na etapa 17 por IDs recebidos mantidos no cliente e reportados em FETCH. Não há ACK separado nem réplica global instantânea de consumo; detalhes e limites na entrega da etapa 17 abaixo.
- Não estão implementadas validações de pertencimento do tópico a T1/T2 nem validação completa de IDs/tipos nos modelos. O roteiro da etapa 05 menciona validações mais amplas; não afirmar que isso já está coberto. Não corrigir fora do escopo sem necessidade/autorização.
- Base herdada tem `_SAT_BY_FACE`, `_DOCKED_SATS`, `HUB_SPIN_STATE` e métricas globais. Não usar esses padrões para nova comunicação Pub/Sub. Migração ampla da base não foi autorizada.
- Identidade corrigida na etapa 18: main usa o número da chave sensor_N de SENSOR_POSITIONS como ID lógico explícito. sender_id continua sendo o ID do rádio. Não existe mais o deslocamento node_id - 1.
- Satélites atuais começam no dock e viajam para fora; a especificação pede início afastado. Não foi corrigido; acompanhar ao integrar mobilidade sem reescrever o protocolo.
- `CoreDockMixin.route_in_core` vazio sombreia métodos posteriores; entrada real do SwCore é `on_dock_upload`.
- `deliver_on_alignment=False` não bloqueia `_try_deliver`, que pode entregar por face sem consultar `_rt`. Documentado, não corrigido.
- SwCore remove buffer ao enviar sem esperar confirmação de próximo salto/entrega final. Seus ACKs de upload não equivalem a confirmação de leitura Pub/Sub.
- `--force-regen` é aceito mas não utilizado. Não corrigido.
- Visualização verde teve teste de chamada ao controlador, não inspeção manual no navegador.

## Testes e comandos úteis

Executar a partir de `tarefa2`:

```powershell
../.venv/Scripts/python.exe -B tests/run_pubsub_tests.py
../.venv/Scripts/python.exe -B -m unittest discover -s tests -v
../.venv/Scripts/python.exe -B -m src.main --pubsub --no-viz
../.venv/Scripts/python.exe -B -m src.main --no-viz --topology star --routing-strategy swcore
```

- Último resultado: **146 testes passaram**, incluindo oito novos da etapa 21; suíte local: **49 testes**, runner verifica que nenhum módulo `gradysim` foi importado.
- Transporte testado com três nós em posições 0/25/50 m, rádio 30 m: origem e destino não têm alcance direto, e a entrega exige dois saltos via hub. Testes incluem envio direto/local, duplicação, ausência de vizinhos, destino desconhecido, TTL e opt-in das fábricas.
- Validação etapa 12: duas execuções independentes de 300 segundos (com/sem Pub/Sub) tiveram **55 uploads e 53 entregas satélite–satélite**, com os mesmos IDs, instantes de criação/entrega e saltos. Isso valida preservação do tráfego original; não são publicações Pub/Sub.
- Logs `verification-*.log` e `.cache/` são ignorados. PowerShell pode rotular saída stderr normal do logging/unittest como `NativeCommandError` na redireção: conferir exit code e resultado real antes de diagnosticar falha.
- Testes de modelos/stores/serviço: `test_pubsub_models.py`, `test_topic_store.py`, `test_subscription_store.py`, `test_consumption_store.py`, `test_pspeer_service.py`, `test_pubsub_regression.py`. Testes de rede/designação: `test_pubsub_transport.py`, `test_pspeer_designation.py`. Outros testes cobrem CLI, estrutura, arquitetura herdada e logging.

## Retomada mínima

1. Ler este resumo e verificar `git status --short tarefa2`.
2. Aguardar/seguir a etapa explicitamente solicitada pelo usuário; a próxima prevista é 22.
3. Para 22, preparar o cenário integrado com três peers, publicações, filtros, sincronização, histórico e reconexão; executar ciclo relevante de todos os satélites e validar logs, sem antecipar métricas definitivas ou runner das etapas posteriores.
4. Implementar e testar somente a etapa; apresentar resumo curto e parar para revisão/commit.

## Entrega da etapa 13

- `adapter.py` implementa o cliente com seleção explícita de um único PSPeer (`select_pspeer`) e APIs `subscribe_pubsub`, `publish_pubsub`, `fetch_pubsub`. Sem seleção ou rota retorna False.
- A composição agora inclui `PubSubAdapterMixin` antes do transporte, resolvendo o despacho apesar da posição de PSPeerMixin na MRO. As observações anteriores sobre o hook do transporte são históricas.
- Somente PSPeers processam requisições. FETCH responde com DELIVER pelo rádio, inclusive resultados vazios; o cliente recebe pelo callback `on_pubsub_delivery`. O callback padrão não retém dados. Consultas não marcam consumo. SYNC é ignorado.
- Sem sincronização, entrega espontânea, ACK, retry, seleção automática ou integração de satélites. Identidades inconsistentes são descartadas.
- Logs INFO de operações/respostas e DEBUG de saltos. Sete testes novos comprovam ida e volta via hub, filtros, repetição sem consumo, falta de seleção, perda de assinatura, destino não peer e composição das fábricas.
- Validação: 90 testes passaram; simulação completa `--pubsub --no-viz` chegou a 300 s sem erros. Não repetida a comparação detalhada de tráfego original da etapa 12.
- Arquivos: novo adaptador, `uav.py`, `transport.py`, `test_pubsub_adapter.py`, README e este resumo. Nenhum commit ou comando de staging executado pelo agente.

## Entrega da etapa 14

- SUBSCRIBE com filtro alterado produz um delta SYNC; repetição idêntica não gera envio. Cada peer tem relógio e versões próprios, sem estado compartilhado entre nós.
- Ordenação por `(version, sender_id)` rejeita duplicatas e versões antigas por assinatura e resolve empates concorrentes deterministicamente. Não representa ordem cronológica real. SYNC recebido não gera outro SYNC.
- Broadcast único `pubsub_sync` usa rádio simulado com alcance específico de 59,5 m. O handler local é instalado somente com `--pubsub`; tráfego comum mantém 30 m. Sem ACK, retry ou reparação de perdas: réplicas podem ficar divergentes, inclusive se o cliente repetir um filtro inalterado.
- Publicações e consumo não são sincronizados. Os limites descritos na entrega da etapa 13 quanto à ausência de sincronização são históricos.
- Validação: 99 testes gerais e 45 locais passaram (os locais fazem parte dos 99). Nove novos testes cobrem versões, concorrência, consumo preservado, três réplicas via rádio, duplicatas, perdas, alcance e descarte por não peer. Simulação completa com Pub/Sub chegou a 300 s sem erros; os eventos SYNC foram exercitados nos testes dedicados, pois o cenário padrão ainda não gera assinaturas espontâneas.
- Arquivos: modelos, serviço, adaptador, transporte, novo `radio.py`, `main.py`, configuração, dois novos arquivos de testes, runner local, README e este resumo. Sem início da etapa 15.

## Entrega da etapa 15

- Política de replicação explicitamente confirmada pelo usuário: armazenar a publicação e fazer um broadcast aos demais peers, pelo mesmo alcance ampliado do SYNC, em mensagem separada. Receptores deduplicam por ID, sem repropagar, ACK ou retry; perdas podem deixar históricos distintos.
- Novo `ReplicateEnvelope(sender_id, publication)` e operação REPLICATE. O emissor é o PSPeer; `publication.origin_id`, região, tópico, timestamp e payload são preservados. Pacote externo `pubsub_replicate`, comando de rádio `ReplicateBroadcastCommand`.
- Adaptador emite réplica somente quando `service.publish()` aceita um PUBLISH novo. Réplicas recebidas só são armazenadas; nós sem serviço descartam. Primeira cópia por ID prevalece localmente, inclusive quando outro conteúdo chega com o mesmo ID. Republicar um ID já conhecido não repara perdas.
- Não há entrega espontânea nem consumo distribuído. Os trechos das entregas anteriores que dizem que publicações não são replicadas são históricos.
- Validação: 105 testes gerais passaram, incluindo seis novos de rádio; 45 locais passaram sem importar GrADyS-SIM (subconjunto dos 105). Testes publicam por um cliente em A e consultam via rádio em B/C/A, verificam filtros, conteúdo original, duplicatas, ingresso repetido por outro peer, perdas parciais/totais e atraso. Simulação padrão com Pub/Sub concluiu 300 s sem erros; eventos de replicação são exercitados pelos testes, pois ainda não há geração espontânea no cenário padrão.
- Arquivos: modelos, adaptador, transporte, rádio, comentário de configuração, teste de modelos, novo `test_pubsub_replication.py`, README e continuidade. Nenhum commit/staging ou implementação da etapa 16.

## Entrega da etapa 16

- `PSPeerService.delivery_subscribers(publication, peer_id)` seleciona tópico/região e responsabilidade pelo emissor da versão vigente da assinatura. Primeiro armazenamento de PUBLISH ou REPLICATE gera push somente aos assinantes sob responsabilidade local. Réplicas continuam sem repropagação.
- `DeliverEnvelope.is_push=False` preserva o contrato FETCH; True indica entrega espontânea. Cliente aceita apenas peer selecionado e destinatário próprio, verifica o filtro local e deduplica push por message_id. FETCH explícito continua podendo retornar IDs repetidos. Nenhum envio ou recebimento marca consumo no servidor.
- `satellite_client.py` adiciona cliente opt-in na fábrica e no main. Usa `_ack_node` somente durante EXCHANGE; não cria rota ou registro global. Core encaminha pelo `_rt` SwCore existente e rádio unicast. Sem alteração da mobilidade, mensagens originais de dock, métricas de sensores ou condição de partida.
- Limitações para a etapa 17: sem buffering Pub/Sub, retry, FETCH automático ou confirmação de consumo. Mudança apenas de `selected_pspeer` não transfere responsabilidade; filtro idêntico não cria versão nova. Perda de SYNC/REPLICATE ou partida durante o envio pode impedir entrega. Histórico continua consultável via FETCH; assinatura tardia não gera push retroativo nesta etapa.
- Validação: 112 testes gerais e 45 locais passaram (locais são subconjunto). Sete novos testes cobrem TF01/02/03, três peers responsáveis por destinatários distintos, satélite em três saltos, duplicata com novo ID de transporte, desconexão, perda sem consumo/retry e composição opt-in da fábrica. Testes antigos de FETCH foram ajustados para observar respostas de consulta separadamente do novo push.
- Simulação padrão com Pub/Sub concluiu 300 s sem erros. O cenário padrão ainda não gera assinaturas/publicações; os eventos Pub/Sub foram exercitados nos testes dedicados. Não foi repetida a comparação detalhada de métricas da etapa 12.
- Arquivos: modelos, serviço, adaptador, transporte, novo cliente de satélite, fábricas/main, novo `test_pubsub_push.py`, ajustes nos testes de adaptador/replicação, README e continuidade. Nenhum commit/staging ou início da etapa 17. As afirmações históricas sobre ausência de push/cliente de satélite nas entregas anteriores não descrevem mais o estado atual.

## Entrega da etapa 17 — contratos atuais

Esta seção substitui as limitações históricas das etapas anteriores quanto a FETCH, consumo, troca de peer e buffering.

- `FetchEnvelope.received_ids` contém IDs confirmados pelo cliente para aquele tópico, normalizados/deduplicados/ordenados. Dados antigos sem esse campo continuam válidos. O adaptador registra IDs localmente só após retorno bem-sucedido de `on_pubsub_delivery`, tanto para push quanto para FETCH. Duplicatas não chegam novamente ao callback; respostas FETCH vazias continuam chegando.
- Cada FETCH leva o conjunto completo de IDs recebidos ao peer escolhido. `report_received` faz merge idempotente antes da consulta e preserva IDs ainda não presentes no histórico, cobrindo réplica tardia. `mark_consumed` local mantém o contrato anterior para IDs desconhecidos. Envios e retirada de buffer nunca significam consumo.
- Consumo é confirmado pelo cliente no próximo FETCH, não por ACK separado ou broadcast de estado de leitura. Peers ainda não consultados podem ter estado antigo; cliente filtra duplicatas. Relatório perdido é repetido no próximo FETCH. Sem tolerância a reinício do cliente e sem garantia de entrega diante de perdas contínuas ou publicação ausente no peer.
- Selecionar outro peer executa `resume_pubsub`: reenvia assinaturas conhecidas e faz FETCH com IDs recebidos. Mesmo filtro em outro peer gera versão nova para transferir responsabilidade; mesmo filtro no proprietário atual não gera SYNC. Satélite offline retoma no próximo contato.
- `PubSubSatelliteMixin._start_exchange` chama a implementação original e então retoma Pub/Sub. Mantém movimentação, upload original, timeout e partida. Nenhuma nova assinatura aleatória é criada.
- `_core_buffer` existente guarda DELIVER pendente para satélite conhecido sem rota utilizável, em chaves `pubsub-buffer:*`, sem `dest_face`, com `pubsub_packet`. `_buffered_for` exclui essas entradas do caminho dock original. Hooks cooperativos de conexão/atualização SwCore drenam a fila via rádio Pub/Sub. Não há novo buffer global nem alterações na dependência ou no SwCore original.
- `_pubsub_delivery_state` distingue pending/submitted por ID de transporte; ledger do cliente distingue recebimento real. Envio bem-sucedido ao próximo salto retira a entrada, sem confirmar entrega. FETCH recupera mensagens perdidas a partir do histórico disponível. Satélite desconhecido, sem informação de rota, não ganha rota inventada. Ledger e relatórios crescem com o histórico; não há compactação.
- Validação: 121 testes gerais e 48 locais passaram (locais são subconjunto). Nove testes novos: seis cenários TF06 de rádio, dois testes locais de transferência/consumo tardio e um de serialização de recibos. IDs first/offline/last recebidos uma vez em contatos repetidos; cobertos troca de peer, perda de entrega/relatório, remoção do buffer sem consumo e falha de callback. Fixtures longas emitem beacons periódicos para manter rotas válidas.
- Testes antigos foram adaptados ao consumo incremental. Testes de replicação continuam consultando o histórico bruto por envelopes sem relatório de recebimento, isolando replicação do comportamento incremental do cliente.
- Simulação padrão `--pubsub --no-viz` concluiu 300 s sem erros. Eventos Pub/Sub/reconexão foram exercitados nos testes dedicados; ainda não há geração espontânea no cenário padrão. Comparação detalhada de métricas originais da etapa 12 não foi repetida.
- Arquivos: modelos, consumo, serviço, adaptador, transporte, cliente de satélite, novo `test_pubsub_reconnection.py`, testes existentes pertinentes, README e continuidade. Sem commit/staging ou início da etapa 18.

## Entrega da etapa 18

- `make_sensor(name)` vincula cada classe ao ID lógico não negativo extraído da chave canônica `sensor_N` de `SENSOR_POSITIONS`. A ordem dos nós e o ID de rádio não mudam essa identidade. Nomes ambíguos como sensor_01 e IDs negativos são rejeitados. O layout mantém IDs únicos por suas chaves; estabilidade refere-se ao mesmo layout, não a uma associação entre posições físicas de layouts regenerados.
- `SensorProtocol` usa esse ID no nome do payload e nas métricas; usuários diretos do template sem ID configurado usam o próprio ID do nó, sem deslocamento. Pacote conserva packets={sensor_N: contagem} e sender_id de rádio, acrescentando sensor_id lógico. Coleta, contagens, temporizadores e TTL permanecem iguais.
- `topic_for_sensor(id)` usa `SENSOR_TOPIC_BY_PARITY=(T2,T1)` centralizado em config.py. Sensor guarda sensor_topic e registra identidade/tópico em DEBUG. Não gera publicações Pub/Sub nesta etapa.
- Validação: 126 testes passaram, incluindo cinco novos de identidade, paridade, validação de nomes, binding do main com ordem invertida e coleta real pelo rádio. O teste antigo que esperava sensor_-1 foi corrigido. Testes verificam logs das duas paridades e preservação das contagens; o runner local permanece com 48 testes (não foi necessário repeti-lo nesta etapa).
- Arquivos: fábrica de sensores, main, template de sensor, esquema de mensagem, configuração, novo sensor_identity.py, novo test_sensor_identity.py, contrato de arquitetura, README e continuidade. Sem commit/staging e sem antecipar a etapa 19.
- Simulação completa `--pubsub --no-viz` concluiu 300 s sem erros. Não foi repetida a comparação detalhada de métricas da etapa 12.

## Entrega da etapa 19

- Novo `SensorPublicationMixin`, composto apenas nas fábricas de satélite com Pub/Sub. Preserva a coleta original via super e converte cada lote válido por sensor em Publication, somente durante COLLECT_OUT/COLLECT_IN.
- Payload contém sensor_id e packet_count. Tópico pela paridade; origem é o ID do satélite e região sua face N/S/E/W; created_at é o instante da coleta. ID sensor:<satellite_id>:<contador local> não muda enquanto a mensagem aguarda envio. Não há uma publicação por leitura individual: cada lote recebido contém sua contagem.
- Fila `_pending_sensor_publications` é local e independente de packets e `_pending` do upload SwCore original. Entrada no contato executa o protocolo original, retomada Pub/Sub e tentativa de envio dos lotes. Sem peer/contato ou retorno False, retém para outro contato. Retorno True remove após envio ao primeiro salto, sem afirmar recebimento; perdas posteriores não geram retry/ACK. Fila pode crescer durante afastamento e conter coletas ao encerrar a simulação.
- Main fornece apenas o ID real do primeiro PSPeer de PSPEER_SLOTS, obtido de builder.add_node, a cada satélite. É configuração inicial do endpoint, sem registro global de protocolos ou troca direta de stores. A API select_pspeer continua disponível.
- Sem mudança na coleta, contadores, TTL dos sensores, upload original, movimento ou partida. INFO registra lotes e resultado da submissão. Sem --pubsub não há conversão.
- Validação: 132 testes passaram, incluindo seis novos de coleta/radio/replicação, paridades, quatro regiões, retenção dos IDs, perda de envio, preservação do upload/departure e configuração do endpoint. Runner local permanece com 48 testes; não foi necessário repeti-lo nesta etapa.
- Simulação completa com Pub/Sub concluiu 300 s sem erros e registrou 669 operações PUBLISH nos PSPeers a partir das coletas reais. Logs mostram T1/T2 e N/S/E/W. Ainda não há assinantes dinâmicos no cenário padrão; entrega filtrada já tem testes próprios. Não foi repetida a comparação detalhada de métricas da etapa 12.
- Arquivos: novo sensor_publications.py, fábrica uav.py, main.py, novo test_sensor_publications.py, README e continuidade. Sem commit/staging ou avanço para a etapa 20. Afirmações históricas sobre ausência de geração de publicações dos sensores não descrevem mais o cenário atual.

## Entrega da etapa 20

- Novo `CorePublicationMixin` apenas na composição opt-in do core, antes do adaptador. Timer pubsub_core_publish inicia após PUBSUB_PUBLICATION_INTERVAL e se repete nesse intervalo. Intervalos não positivos ou não finitos são rejeitados.
- RNG exclusivo de cada nó: random.Random com semente textual formada por PUBSUB_SEED, prefixo core e ID do nó. Não usa o RNG global nem altera as sementes de mobilidade/sensores. Mesmo seed/IDs produzem mesmas sequências independentemente da ordem entre nós.
- Cada evento escolhe um tópico de PUBSUB_TOPICS, região C, created_at atual, payload com value aleatório em [0,1) e ID core:<node_id>:<contador>. Não cria assinaturas; TF04 é validado com assinaturas explícitas no teste.
- PSPeers começam selecionando a si próprios. No main, classes dos demais cores recebem apenas o ID real do primeiro PSPeer configurado, antes da construção da simulação; sem registro global de instâncias ou acesso direto a stores. API de troca de peer continua válida.
- Falha de submissão é registrada e o próximo evento continua normalmente. Não há buffer/retry para essas publicações; envio ao primeiro salto não é confirmação de entrega. Logs INFO informam ID, tópico, região, peer e submissão.
- Validação: 138 testes passaram, seis novos de geração determinística, independência do RNG global, intervalos/IDs/região, configuração inválida, composição opt-in e TF04 (e filtro incompatível) via rádio. Runner local permanece com 48 testes; não foi necessário repeti-lo nesta etapa.
- Simulação completa com Pub/Sub concluiu 300 s sem erros e registrou 540 publicações geradas pelos nove nós do core (60 por nó), além das publicações dos sensores. Cenário padrão ainda não possui assinaturas espontâneas; entrega filtrada foi exercitada nos testes. Sem repetição da comparação detalhada de métricas da etapa 12.
- Arquivos: novo core_publications.py, composição uav.py, configuração inicial main.py, comentário de semente em config.py, novo test_core_publications.py, README e continuidade. Sem commit/staging ou início da etapa 21.

## Entrega da etapa 21

- Novo `DynamicSubscriptionMixin` somente nas fábricas Pub/Sub de core e satélites. Timer pubsub_subscribe usa PUBSUB_SUBSCRIPTION_INTERVAL, começando após um intervalo; rejeita valores não positivos/não finitos.
- RNG por instância com seed textual PUBSUB_SEED:subscriptions:<node_id>, separado do RNG de publicações e do RNG global. A cada evento escolhe T1/T2 e subconjunto não vazio de N/S/E/W/C. Preserva a assinatura do outro tópico; ambos podem coexistir.
- Core envia SUBSCRIBE e, se submetido, FETCH do histórico. Satélite em EXCHANGE faz o mesmo; afastado mantém o último filtro por tópico em `_client_subscriptions`, sem transmitir. A retomada existente envia os filtros atuais e consulta histórico no contato; filtros intermediários offline são substituídos.
- Correção necessária encontrada na validação: eventos de rádio no mesmo instante podem entregar FETCH antes de SUBSCRIBE. `FetchEnvelope.subscription` opcional carrega o filtro local vigente, validando tópico e assinante. Peer aplica esse filtro e consulta o histórico na mesma requisição, sem ACK adicional. Campo ausente mantém compatibilidade. FETCH também recupera uma assinatura cujo SUBSCRIBE se perdeu; recibos/consumo continuam preservados.
- Logs INFO registram nó, tópico, regiões ordenadas, peer e submissão. Nenhuma alteração nos geradores de publicações, mobilidade ou partida.
- Validação: 146 testes gerais e 49 locais passaram (locais são subconjunto). Oito novos: sete testes de assinaturas (semente, filtros, coexistência de tópicos, intervalos, opt-in, TF05/histórico, contato offline e chegada sem SUBSCRIBE, agrupados em sete métodos) e um de serialização/validação de FETCH com filtro. Teste antigo de perda de assinatura atualizado para a recuperação pelo FETCH.
- Simulação completa de 300 s concluída sem erros após a correção de ordem, com 780 eventos de assinatura (60 por cada um dos 13 UAVs). A primeira execução foi repetida porque o contrato FETCH foi corrigido durante a validação. Não foi executada a etapa 22 nem repetida a comparação detalhada de métricas da etapa 12.
- Limites mantidos: submissão não confirma entrega; SYNC/REPLICATE podem se perder; consumo não é globalmente instantâneo. Filtros locais são os mais recentes do cliente; não há ordenação causal adicional de múltiplas alterações do cliente em trânsito com atrasos arbitrários.
- Arquivos: novo dynamic_subscriptions.py, composição uav.py, modelos/adapter para FETCH com filtro, novo test_dynamic_subscriptions.py, testes de modelos/adapter, README e continuidade. Sem commit/staging ou início da etapa 22. Descrições históricas sobre ausência de assinaturas espontâneas não representam mais o cenário atual.
