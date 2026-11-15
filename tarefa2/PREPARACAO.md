# Preparação da cópia local

Etapa realizada em 15/11/2026, limitada à cópia do projeto e à validação de execução. Nenhuma funcionalidade Pub/Sub foi implementada.

## Arquivos e independência

Foram copiados 34 arquivos de `routing-ricardo`: `src/`, `utils/`, `README.md`, `requirements.txt` e `.gitignore`. Todos foram comparados por SHA-256 com a origem, sem divergências. Os três documentos de especificação/contexto previamente presentes foram preservados.

Não foram copiados metadados Git, ambientes virtuais, caches, bytecode ou temporários. `results.txt` foi excluído por ser saída de uma execução anterior. Os caches gerados na validação ficam em `tarefa2/.cache`, ignorados pelo Git; não vieram da pasta original.

Os 98 arquivos existentes na origem foram verificados por SHA-256 antes e depois da preparação e permaneceram inalterados. `git diff --exit-code -- routing-ricardo` também não apresentou diferenças.

As pastas são cópias físicas separadas, mas pertencem ao mesmo repositório Git raiz, `getting-started`. Não são dois repositórios Git independentes. O remoto `origin`, para fetch e push, é `https://github.com/INF2541-Intro-Mobile-Ubiquous-Computing/leobarros.git`. Não existe remoto configurado apontando para o repositório original `routing-ricardo`. Commits são locais; um push usando a configuração atual tem como destino `leobarros`. Esta verificação não garante o destino caso os remotos sejam alterados futuramente ou um push use uma URL explícita.

Nenhum commit, push, inicialização de repositório ou alteração de remoto foi realizado.

## Verificação

Ambiente utilizado: Python 3.13.15 e GrADyS-SIM (`gradysim`) 0.8.0, já disponíveis no ambiente virtual da raiz. O ambiente não foi copiado nem modificado.

Executados a partir de `tarefa2`:

```powershell
../.venv/Scripts/python.exe -B -m unittest discover -s tests -v
../.venv/Scripts/python.exe -B -m src.main --no-viz --routing-strategy swcore --topology star
```

- Quatro testes passaram: arquivos essenciais; sintaxe de todos os módulos; importação dos módulos e resolução do cache dentro da cópia; ausência de Git aninhado e links nos diretórios de código.
- A simulação terminou com sucesso: 300 segundos simulados e 987366 iterações.
- Logs locais: `verification-tests.log` e `verification-swcore.log`, ignorados pelo Git.

Para configurar um ambiente próprio, seguir o README copiado, criando um `venv` dentro de `tarefa2` e instalando `requirements.txt`. O projeto pode ser executado sem importar arquivos de `routing-ricardo`.

## Limitações desta etapa

O código e o arquivo de dependências foram preservados integralmente. `requirements.txt` declara `gradysim` sem fixar versão; uma instalação nova não foi testada. A visualização no navegador não foi validada.

A configuração original está em `utils/common/config.py` e `utils/viz_templates/constants.py`; não existe `constants.ts` no projeto copiado. Nenhuma migração de configuração foi feita nesta etapa. A arquitetura original, inclusive seus estados globais existentes, foi mantida; estes testes verificam a preparação e a execução, não a conformidade com todos os requisitos futuros de Pub/Sub distribuído.
