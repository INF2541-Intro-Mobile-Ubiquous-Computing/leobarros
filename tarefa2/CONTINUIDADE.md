# Continuidade do projeto Tarefa 2

Atualizado em 15/11/2026, após implementar a etapa 13. Leia este arquivo primeiro na nova conversa; depois, apenas os trechos de código relevantes à etapa autorizada. Este resumo não autoriza iniciar outra etapa automaticamente.

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

**Etapas 01–13 implementadas e testadas. Próxima: 14, somente após solicitação do usuário.** Os PSPeers processam SUBSCRIBE/PUBLISH/FETCH do core e respondem consultas pelo rádio. Nenhum drone gera eventos espontâneos.

Na preparação deste resumo, as mudanças da etapa 12 estavam **staged pelo usuário**: README, `src/main.py`, `src/uav.py`, `utils/common/config.py`, `src/pubsub/transport.py` e `tests/test_pubsub_transport.py`. Não presumir que o commit ocorreu; consultar `git status` sem modificar o índice. Este resumo é uma alteração documental posterior.

| Etapas concluídas | Resultado |
| --- | --- |
| 01–03 | Cópia limpa, baseline SwCore e mapeamento da arquitetura |
| 04 | `--pubsub` força `star` + `swcore`, mesmo diante de opções conflitantes; parâmetros centralizados |
| 05–06 | Modelos/envelopes e `TopicStore` |
| 07–08 | `SubscriptionStore` e `ConsumptionStore` |
| 09–10 | `PSPeerService`, regressões e suíte local independente do simulador |
| 11 | Três rims com serviço PSPeer próprio, identificação INFO e cor verde |
| 12 | Transporte core–core opt-in, direto ou via hub, com rádio simulado e callback de recepção |

## Contratos implementados

Arquivos em `src/pubsub/`:

- `models.py`: dataclasses `Publication(message_id, topic, origin_id, origin_region, created_at, payload)` e `Subscription(subscriber_id, topic, accepted_regions)`. Regiões N/S/E/W/C. Filtro normalizado para `frozenset`. Dataclasses frozen, mas payload é mutável; não presumir imutabilidade profunda.
- Envelopes: `SubscribeEnvelope(sender_id, subscription)`, `PublishEnvelope(sender_id, publication)`, `FetchEnvelope(sender_id, subscriber_id, topic)`, `DeliverEnvelope(sender_id, subscriber_id, publications)` e `SyncEnvelope(sender_id, subscriptions)`. Todos usam `msg_type='pubsub'` e operação explícita. `to_json/to_dict` e `envelope_from_json/envelope_from_dict`; serialização determinística, regiões ordenadas.
- `SyncEnvelope` atualmente transporta **somente assinaturas**, sem versão/ID de atualização. Será necessário estender na etapa apropriada.
- `topic_store.py`: `TopicStore.add_publication()` retorna True se inseriu, False se ID já existe em qualquer tópico da mesma instância; primeira versão prevalece. `get_history(topic)` devolve snapshot em tupla, ordem de chegada, mantendo `created_at`; cópias profundas na entrada/consulta.
- `subscription_store.py`: `matches(subscription, publication)` exige tópico igual e região aceita. `add_subscription()` insere/substitui filtro por `(subscriber_id, topic)`, retornando se mudou. `get_subscription()` e `get_matching_subscriptions()`.
- `consumption_store.py`: recebe stores locais no construtor; `get_unread(subscriber_id, topic)` retorna histórico elegível não consumido. Consultas não alteram estado. `mark_consumed(subscriber_id, topic, message_id)` registra confirmação explícita; False para assinatura/ID desconhecido ou repetição. Não confere filtro atual, permitindo confirmação tardia após troca do filtro. O chamador é responsável por confirmar recebimento real. Não há ACK de rede.
- `pspeer_service.py`: cada `PSPeerService()` cria seus próprios stores; API `subscribe`, `publish`, `fetch`, `mark_consumed`. Ainda sem processamento de envelopes, seleção de peers, replicação ou envio automático.
- `pspeer_mixin.py`: `PSPeerMixin.initialize()` chama `super`, cria `self.pspeer_service` e registra INFO com ID e slot. Atributos `is_pspeer=True`, `pspeer_slot`.
- `transport.py`: `PubSubTransportMixin` sobre `SWCoreMixin`, ativo somente no core com `--pubsub`. `send_pubsub(destination, envelope) -> bool`; `handle_pubsub(envelope, source_id)` é hook de recepção que atualmente só registra DEBUG.

### Transporte e composição

`src/uav.py` monta o roteamento opt-in como `PubSubAdapterMixin, PubSubTransportMixin, SWCoreMixin`. Nas fábricas, vêm antes deles `NeighborMixin` e `CoreDockMixin`; o protocolo rim inclui `PSPeerMixin` quando selecionado. Atenção à MRO: adicionar `handle_pubsub()` apenas no `PSPeerMixin`, que está depois do transporte, não sobrescreve automaticamente o hook do transporte. Inspecionar o ponto de despacho na etapa 13.

O transporte core usa os beacons/fresh_neighbors existentes e `_send()` do SwCore. Destino vizinho recebe diretamente; caso contrário, vai ao hub conhecido. O hub encaminha para o destino vizinho. Sem próximo salto, retorna False; um intermediário sem rota descarta. Não há discovery extra, retry, buffering Pub/Sub core–core ou confirmação. True significa envio ao próximo salto, **não entrega**. Destino próprio despacha localmente, sem unicast a si mesmo.

O envelope externo `pubsub_core` contém `transport_id` por origem/contador, `source_id`, destino, saltos, próximo salto e payload da aplicação. Deduplicação por instância e limite de saltos. O emissor de aplicação permanece no envelope interno. Esse caminho suporta o core em estrela; **não é uma solução de roteamento arbitrário nem entrega Pub/Sub a satélites**. O caminho satélite–satélite original foi preservado.

## Parâmetros e logs

Em `utils/common/config.py`: `PUBSUB_ENABLED=False`, tópicos T1/T2, `PSPEER_SLOTS=(0,3,6)` (índices de rims, nunca IDs dinâmicos), `PSPEER_COLOR=(0,200,100)`, `PUBSUB_SEED=2056`, intervalos de publicação/assinatura de 5 s e `PUBSUB_TRANSPORT_MAX_HOPS=8`. Semente/intervalos Pub/Sub ainda não geram eventos. Validam-se três slots distintos, inteiros e dentro da borda.

Por pedido do usuário, todos os logs detalhados preexistentes da aplicação foram movidos para DEBUG. `LOG_LEVEL='INFO'` mantém início/fim/tempo total e identificação dos três PSPeers. Novos logs INFO de aplicação poderão ser acrescentados conforme as etapas pedirem, sem restaurar o ruído antigo.

`utils/common/logging_config.py` reaplica nível e filtros antes/depois de `builder.build()`. GrADyS-SIM redefine nível e adiciona handler; a configuração local conserva somente o mais recente handler de console do simulador, eliminando duplicação `INFO:root:`/`INFO`. Preserva handlers de arquivo/customizados. Logs informativos internos da biblioteca viram DEBUG, exceto início/fim/tempo total; erros/avisos da biblioteca continuam visíveis. Não editar a dependência.

## O que falta no roteiro

| Etapa | Escopo e validação principal |
| --- | --- |
| 13 — concluída | Comunicar UAVs e PSPeers: processar SUBSCRIBE/PUBLISH/FETCH pelo adaptador. Cliente conhece apenas o PSPeer escolhido. Testar um UAV assinando, publicando e consultando através do rádio, com logs comprovando o caminho. Não antecipar sincronização. |
| **14 ? pr?xima** | Sincronizar assinaturas: SYNC após alteração local; peers aplicam, demais cores descartam; sem repropagar, ACK ou retransmitir. ID/versão idempotente. Testar três réplicas e perdas. Resolver alcance multicast antes da implementação. |
| 15 | Distribuir/replicar publicações entre PSPeers, deduplicar e evitar ciclos, separadamente de assinaturas. Publicar em A e consultar B/C. **Política de replicação ainda precisa ser confirmada**, pois é proposta do roteiro, não exigência inequívoca da especificação. |
| 16 | Entrega aos assinantes elegíveis via DELIVER/SwCore, destino individual, sem expor assinantes ao publicador. Considerar satélites disponíveis e deduplicação. TF01/02/03. |
| 17 | Reconexão e consumo incremental: FETCH ao conectar, reutilização de buffers SwCore, distinguir pendente/enviado/recebido. TF06 com IDs exatos e reconexões repetidas. Resolver confirmação/controle distribuído de consumo. |
| 18 | Identificação única/estável de sensores; par→T2, ímpar→T1, preservando coleta original. Testar/logar ambas as paridades. |
| 19 | Converter coleta dos satélites em publicações reais por tópico/paridade e região N/S/E/W; armazenar durante afastamento e transmitir no contato. |
| 20 | Timers de publicações aleatórias do core em T1/T2, região C, semente reproduzível; entrega conforme filtro. TF04. |
| 21 | Assinaturas dinâmicas de core/satélites, tópico e subconjunto de regiões por semente; satélites enviam no contato; permitir ambos os tópicos. Histórico elegível e TF05. |
| 22 | Cenário integrado com três peers, eventos dinâmicos, filtros, sincronização, histórico e reconexão. Logs estruturados. Executar ciclo relevante de todos os satélites. |
| 23 | Automatizar TF01–TF06 usando comunicação real simulada, não apenas chamadas locais. Executar isolados/juntos; TF06 verifica IDs, não só contagem. |
| 24 | Métricas por (publicação, assinante): entregas, latência, saltos; separar controle, sincronização, retransmissões SwCore e duplicatas. Validar denominadores em cenários pequenos. |
| 25 | Runner reproduzível com semente/duração/parâmetros e exportação CSV/JSON; repetir sementes e comparar resultados. Métricas definitivas dependem do professor. |
| 26 | README final, instalação/execução/testes/parâmetros/limitações/métricas, diagrama e responsabilidades; validar ambiente limpo e autonomia da pasta tarefa2. |

Marcos: M2 (lógica local) concluído na 10; M3 assinaturas sincronizadas na 14; M4 rede/reconexão na 17; M5 integração na 22; M6 entrega na 26.

## Questões importantes ainda não resolvidas

- Rádio de 30 m e raio do core de 29,25 m: rims opostos estão a 58,5 m. Um broadcast original não atinge todo o core; a especificação assume alcance suficiente para SYNC sem retransmissão. Não substituir silenciosamente por flooding; definir o mecanismo na 14.
- Semântica de confirmação/consumo: consultas nunca marcam consumo; o estado local existe, mas nenhum mecanismo de rede o confirma. O roteiro alerta para não inventar garantia de entrega. Como manter leitura ao trocar de PSPeer também exige atenção nas etapas de integração.
- Não estão implementadas validações de pertencimento do tópico a T1/T2 nem validação completa de IDs/tipos nos modelos. O roteiro da etapa 05 menciona validações mais amplas; não afirmar que isso já está coberto. Não corrigir fora do escopo sem necessidade/autorização.
- Base herdada tem `_SAT_BY_FACE`, `_DOCKED_SATS`, `HUB_SPIN_STATE` e métricas globais. Não usar esses padrões para nova comunicação Pub/Sub. Migração ampla da base não foi autorizada.
- Nome do sensor no payload é `sensor_{node_id - 1}`; sensores são adicionados primeiro, portanto nó 0 vira `sensor_-1`. Corrigir identidade na 18; não confundir com chaves de `SENSOR_POSITIONS`.
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

- Último resultado: **90 testes passaram**, incluindo oito de transporte com rádio/timers reais; suíte local: **40 testes**, runner verifica que nenhum módulo `gradysim` foi importado.
- Transporte testado com três nós em posições 0/25/50 m, rádio 30 m: origem e destino não têm alcance direto, e a entrega exige dois saltos via hub. Testes incluem envio direto/local, duplicação, ausência de vizinhos, destino desconhecido, TTL e opt-in das fábricas.
- Validação etapa 12: duas execuções independentes de 300 segundos (com/sem Pub/Sub) tiveram **55 uploads e 53 entregas satélite–satélite**, com os mesmos IDs, instantes de criação/entrega e saltos. Isso valida preservação do tráfego original; não são publicações Pub/Sub.
- Logs `verification-*.log` e `.cache/` são ignorados. PowerShell pode rotular saída stderr normal do logging/unittest como `NativeCommandError` na redireção: conferir exit code e resultado real antes de diagnosticar falha.
- Testes de modelos/stores/serviço: `test_pubsub_models.py`, `test_topic_store.py`, `test_subscription_store.py`, `test_consumption_store.py`, `test_pspeer_service.py`, `test_pubsub_regression.py`. Testes de rede/designação: `test_pubsub_transport.py`, `test_pspeer_designation.py`. Outros testes cobrem CLI, estrutura, arquitetura herdada e logging.

## Retomada mínima

1. Ler este resumo e verificar `git status --short tarefa2`.
2. Aguardar/seguir a etapa explicitamente solicitada pelo usuário; a próxima prevista é 14.
3. Para 14, resolver primeiro o alcance do SYNC; consultar adaptador, transporte, modelos e stores relevantes.
4. Implementar e testar somente a etapa; apresentar resumo curto e parar para revisão/commit.

## Entrega da etapa 13

- `adapter.py` implementa o cliente com seleção explícita de um único PSPeer (`select_pspeer`) e APIs `subscribe_pubsub`, `publish_pubsub`, `fetch_pubsub`. Sem seleção ou rota retorna False.
- A composição agora inclui `PubSubAdapterMixin` antes do transporte, resolvendo o despacho apesar da posição de PSPeerMixin na MRO. As observações anteriores sobre o hook do transporte são históricas.
- Somente PSPeers processam requisições. FETCH responde com DELIVER pelo rádio, inclusive resultados vazios; o cliente recebe pelo callback `on_pubsub_delivery`. O callback padrão não retém dados. Consultas não marcam consumo. SYNC é ignorado.
- Sem sincronização, entrega espontânea, ACK, retry, seleção automática ou integração de satélites. Identidades inconsistentes são descartadas.
- Logs INFO de operações/respostas e DEBUG de saltos. Sete testes novos comprovam ida e volta via hub, filtros, repetição sem consumo, falta de seleção, perda de assinatura, destino não peer e composição das fábricas.
- Validação: 90 testes passaram; simulação completa `--pubsub --no-viz` chegou a 300 s sem erros. Não repetida a comparação detalhada de tráfego original da etapa 12.
- Arquivos: novo adaptador, `uav.py`, `transport.py`, `test_pubsub_adapter.py`, README e este resumo. Nenhum commit ou comando de staging executado pelo agente.
