# Geocast mínimo

A região de destino das perguntas é `GEOCAST_REGION = (0, 50, 30, 50)` em
`constants.py`: `0 ≤ x ≤ 50` e `30 ≤ y ≤ 50`, incluindo as bordas. As posições
são coordenadas locais em metros, no plano XY; a altitude não participa.

Todos os drones compartilham essa região fixa. A posição na recepção determina
se o drone responde. Intermediários fora da região continuam encaminhando;
intermediários dentro respondem e encaminham, para alcançar outros destinos.
Os drones finais só respondem dentro da região. Não há espera por entrada
futura na área. As respostas voltam à torre como no exemplo original.

Broadcast continua sendo o transporte local de rádio. O geocast aqui é a
seleção geográfica dos destinatários da pergunta, por filtragem de aplicação,
sem alterar a topologia física. A região é implícita e fixa na configuração;
regiões diferentes por mensagem exigiriam um cabeçalho adicional.

Essa escolha segue a noção de destino por área e filtragem de entrega da
[RFC 2009, seções 2a e 3b-i](https://www.rfc-editor.org/rfc/rfc2009.html).
Não se trata de uma implementação completa dessa RFC experimental.

## Executar

Com um ambiente Python 3.13.5 contendo GrADyS-SIM 0.8.0 e websockets 17.1:

```powershell
python geocast/main.py
python -m unittest discover -s geocast -p test_geocast.py -v
```

No runtime embarcado já preparado neste workspace, a partir da raiz:

```powershell
.\.runtime\python-3.13.5\python.exe .runtime\run_example.py geocast
.\.runtime\python-3.13.5\python.exe -c "import sys, unittest; sys.path.insert(0, 'geocast'); unittest.main(module='test_geocast', verbosity=2)"
```

O auxiliar local `run_example.py` seleciona explicitamente a pasta, pois o
runtime embarcado anterior contém `dtn` no seu caminho de importação. Ele não
altera `main.py`. A opção `--slow` apenas reduz a velocidade para 1× na inspeção.

Abra o [visualizador original](https://project-gradys.github.io/gradys-sim-nextgen-visualization/)
antes da execução. `main.py` mantém 20 segundos e velocidade 5×; a duração real
pode aumentar com o custo de processamento da visualização.

## Limites preservados

O encaminhamento segue os níveis originais e pode perder mensagens por falta
de contato ou falha de rádio. Não há DTN, deduplicação ou garantia de entrega.
A torre pode receber a mesma resposta por caminhos diferentes. Cores de
intermediários indicam tráfego encaminhado, inclusive fora da região, e não
necessariamente entrega à aplicação. A área não é desenhada na cena, mantendo
a apresentação original sem mudanças adicionais.

Veja [PLANO.md](PLANO.md) e [VERIFICACAO.md](VERIFICACAO.md).
