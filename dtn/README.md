# DTN mínima

Cópia independente de `broadcast`, com armazenamento em memória, transporte
durante movimento e retransmissão periódica. O plano está em [PLANO.md](PLANO.md).

As mensagens originais recebem apenas ID e expiração:
`[0][ID=0:1][EXP=65][PERGUNTA] ...`. Cada mensagem tem TTL de 60 segundos
contados de sua criação; o prazo não é renovado nos saltos. Respostas têm
seu próprio ID e TTL, sem correlação adicional com perguntas.

A torre cria e reenvia perguntas no timer original de 5 segundos. Os drones
mantêm a fila original e reenviam no timer de mobilidade de 2 segundos.
O drone final continua respondendo imediatamente e guarda a resposta para
novas tentativas. Duplicatas não provocam novo processamento nem nova resposta.
Perguntas sobem de nível e respostas descem, como em `broadcast`.

As filas descartam mensagens expiradas no próximo envio; registros de IDs
expirados são limpos na próxima tentativa de aceitação. O estado é volátil.
`main.py` e os dois arquivos de mobilidade são idênticos aos originais.

Os textos de perguntas e respostas foram preservados do exemplo original;
são conteúdo fictício da simulação, sem significado para o protocolo.

## Execução

Na raiz do projeto, com o runtime Python 3.13.5 preparado nesta verificação:

```powershell
.\.runtime\python-3.13.5\python.exe dtn\main.py
.\.runtime\python-3.13.5\python.exe -m unittest discover -s dtn -p test_dtn.py -v
```

Esse runtime oficial embarcado está em `.runtime` (ignorado pelo Git). Seu
`python313._pth` inclui `../../.venv/Lib/site-packages`, `../../dtn` e
`import site`, reutilizando as dependências existentes: GrADyS-SIM 0.8.0 e
websockets 17.1. O interpretador da `.venv` continua sendo 3.13.15.
Em outra máquina, crie um ambiente Python 3.13.5, instale `gradysim==0.8.0`
e `websockets==17.1` e execute `python dtn/main.py`.

Abra o [visualizador GrADyS-SIM](https://project-gradys.github.io/gradys-sim-nextgen-visualization/)
antes de iniciar. A configuração padrão mantém 20 segundos simulados e
velocidade 5×, portanto a execução dura aproximadamente 4 segundos reais.
## Limites

É um exemplo didático, sem ACK, custódia ou armazenamento em disco. A entrega
depende de uma sequência de contatos antes do TTL e não é garantida. Manter
cópias até o TTL simplifica o protocolo, mas aumenta transmissões. IDs são
únicos por execução (nó + sequência); reinícios persistentes não são tratados.
