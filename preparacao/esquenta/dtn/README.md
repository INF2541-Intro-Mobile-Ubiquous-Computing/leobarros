# DTN com descoberta por HELLO

Os nós guardam mensagens em memória enquanto se movimentam. A cada 2 segundos,
`NodeProtocol.handle_timer()` transmite `[HELLO=id_do_no]` por broadcast.
Ao receber um HELLO válido de outro nó, `handleHello()` envia toda a fila por
unicast (`SEND`) ao emissor do anúncio. Cada item sai da fila após a chamada de
envio retornar. Não há ACK, TTL, níveis nem reenvio periódico de dados.

As mensagens usam `[ID=nó:sequência][PERGUNTA] ...` ou
`[ID=nó:sequência][RESPOSTA] ...`. `createMessage()` registra os IDs locais;
`acceptMessage()` rejeita IDs já conhecidos, inclusive após o encaminhamento.
`scheduleForwardMessage()` guarda uma mensagem para o próximo HELLO.

A torre cria perguntas a cada 5 segundos. Os drones intermediários armazenam
perguntas e respostas novas. Os drones finais respondem uma vez por pergunta,
guardando a resposta até receber um HELLO. A torre consome respostas novas.
O timer de mobilidade movimenta os drones, sem enviar dados. Os contadores
`sent` e `received` contam dados, sem incluir anúncios HELLO.

## Limites da simplificação

Sem confirmação, transmitir significa tentar enviar, não comprovar entrega.
Perdas ou afastamento após o HELLO podem eliminar a única cópia em trânsito.
O primeiro vizinho que anuncia presença recebe toda a fila, sem seleção de rota:
se já conhece a mensagem, rejeita a duplicata e a propagação pode terminar.
No cenário original estendido a 80 segundos, com semente 7 e perda de 10%,
a verificação desta versão não entregou respostas à torre. Um teste integrado
com contato direto e sem perdas confirma a entrega de perguntas e respostas.

Sem HELLO, as mensagens ficam na fila indefinidamente. Os IDs vistos permanecem
em memória durante toda a execução. Não há persistência em disco; reinícios
apagam filas e registros. IDs são únicos por nó e sequência dentro da execução.

## Execução

Na raiz do projeto:

```powershell
.\.runtime\python-3.13.5\python.exe preparacao\esquenta\dtn\main.py
.\.runtime\python-3.13.5\python.exe -m unittest discover -s preparacao/esquenta/dtn -p test_dtn.py -v
```

`main.py` mantém a configuração e a visualização existentes.
