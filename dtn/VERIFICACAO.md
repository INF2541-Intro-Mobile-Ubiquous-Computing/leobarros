> Documento histórico da versão com níveis, TTL e retransmissões periódicas.
> O comportamento atual com HELLO está descrito em [README.md](README.md).

# Comparação e verificação da versão simplificada

Esta revisão substitui o relatório da primeira implementação e segue o
[plano revisado](PLANO.md), priorizando diferenças mínimas para `broadcast`.

## Comparação por arquivo

Contagem de linhas textuais adicionadas/removidas em relação a `broadcast`,
sem contar mudanças de terminação de linha:

| Arquivo | Diferença | Motivo |
| --- | --- | --- |
| `main.py` | Idêntico byte a byte | Mesmo `main()`, configuração e handlers |
| `horizontal_uav_protocol.py` | Idêntico byte a byte | Mobilidade original |
| `vertical_uav_protocol.py` | Idêntico byte a byte | Mobilidade original |
| `constants.py` | +2 / −0 | Comentário e TTL de 60 segundos |
| `node_protocol.py` | +29 / −1 | ID, expiração e deduplicação compartilhados |
| `uav_protocol.py` | +8 / −4 | Deduplicar; reter/retransmitir a fila original; identificar resposta auxiliar |
| `tower_protocol.py` | +12 / −3 | Guardar/retransmitir perguntas e deduplicar respostas |
| `final_uav_protocol.py` | +4 / −1 | Deduplicar pergunta, identificar e guardar a resposta imediata |

Total no código de produção: **55 linhas adicionadas e 9 removidas**.
Não foi alterado nenhum arquivo de `broadcast`.

Foram removidos `bundle.py`, JSON, correlação extra de respostas, os métodos
`accepts`/`onBundle`, o timer `retry` e `build_simulation`. Os métodos originais,
comentários, mensagens, regras de nível, temporizadores e pintura permanecem.
A proteção adicional para ausência de telemetria também foi retirada para
manter a mobilidade original: o cenário GrADyS-SIM fornece telemetria antes
do primeiro movimento, como confirmado nas execuções integradas.

## Verificação com Python 3.13.5

**7 testes passaram** em `test_dtn.py`:

- Retenção após perda da pergunta, transporte/reenvio em contato posterior,
  retenção após perda da resposta imediata e entrega à torre.
- IDs duplicados não geram novo processamento ou resposta.
- TTL absoluto preservado no encaminhamento; descarte no limite exato e
  rejeição de cópias atrasadas. Perguntas e respostas expiram independentemente.
- Regras de direção preservadas e rejeição de metadados ausentes/inválidos.
- Igualdade byte a byte dos três arquivos preservados e igualdade das
  constantes originais de configuração visual.
- Pintura cinza/vermelha/azul, tamanho e comandos de mobilidade preservados.
- Execução de `main()` com configuração de teste de 80 segundos, semente 7,
  perda de 10%: **28 respostas únicas na torre** e filas válidas ao final.

As adaptações para execução rápida e captura do simulador ficam exclusivamente
no teste, por substituição temporária de dependências. Não há função de
produção criada para os testes.

Também foi executado `dtn/main.py` diretamente, com o `VisualizationHandler`
real e parâmetros originais: finalizou sem erro aos 20 segundos simulados,
com **4 respostas únicas** nessa execução aleatória. A aparência é preservada
pelo código e pelos testes; esta revisão não inclui uma nova inspeção de
quadros no navegador. A inspeção visual da primeira versão continua apenas
como evidência histórica, não como teste da versão atual.

## Conceito DTN preservado

Os drones não descartam mensagens válidas após transmitir: carregam as cópias
na fila e tentam novamente nos próximos movimentos. A torre repete perguntas
retidas no timer de comunicação. A comunicação entre contatos continua sendo
broadcast, e não exige um caminho completo simultâneo entre torre e destino.

É uma DTN didática, sem ACK, custódia ou disco. Entrega depende de contatos
antes do TTL; não há garantia de entrega. A sequência de IDs vale para uma
execução, sem suporte a reinícios persistentes.
