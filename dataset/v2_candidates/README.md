# Candidatos V2 (área de preparação)

Área de preparação para ampliar o dataset `dataset/v2_real_world/` com bugs reais de Python validados pelos mantenedores dos projetos. **Nada aqui faz parte do dataset ainda.** Todo arquivo desta pasta foi gerado por `scripts/collect_validated_bugs.py` (coleta de 2026-09-29), exceto `pr_sources.json` (entrada manual) e este README.

## Fontes

1. **BugsInPy** (`soarsmu/BugsInPy`, branch master, baixado como zip). Cada bug traz commit com bug, commit corrigido, patch da correção e um teste que falha antes da correção. Os 84 bugs BugsInPy que já estão em `dataset/v2_real_world/ground_truths.json` foram pulados.
2. **Pull requests do GitHub** listados em `pr_sources.json`. Hoje só há um: `amazon-ion/ion-python#448`.

## Critérios de aceitação

Um bug só entra como candidato quando:

- a correção está no histórico oficial do projeto e é comprovada por teste: no BugsInPy, o teste que falha antes do fix; num PR, o PR precisa estar *merged* e alterar ou adicionar um arquivo de teste;
- o patch altera exatamente **um** arquivo Python que não é de teste;
- todas as linhas alteradas nesse arquivo caem dentro de **uma única** função de topo ou método de classe (qualificado como `Classe.metodo`);
- o arquivo com bug pode ser baixado no commit indicado.

Nenhum bug foi inventado ou inferido: arquivo, função e linhas removidas saem do patch oficial.

## Resultado da coleta

### BugsInPy

418 bugs examinados: **199 aceitos**, **219 recusados** (o `bip_pandas_5` foi movido para os recusados depois da checagem abaixo).

| Motivo da recusa | Qtde |
|---|---|
| linhas alteradas fora de uma única função/método | 124 |
| correção em 2 arquivos não-teste | 49 |
| arquivo com bug não baixável | 27 |
| correção em 3 arquivos não-teste | 8 |
| correção em 4 arquivos não-teste | 6 |
| correção em 5 arquivos não-teste | 2 |
| correção em 8 arquivos não-teste | 1 |
| nenhum arquivo Python não-teste alterado | 1 |

Os 27 "não baixáveis" são todos do pandas: o `bug.info` do BugsInPy traz o commit com bug em SHA curto de 7 caracteres, e esses SHAs não resolvem no GitHub (retornam 404 também na página do commit). Não foi usada nenhuma substituição, como o pai do commit corrigido, porque isso trocaria a proveniência declarada.

### Aceitos por projeto

| Projeto | Aceitos | Recusados |
|---|---|---|
| ansible | 4 | 10 |
| black | 10 | 9 |
| cookiecutter | 2 | 1 |
| fastapi | 9 | 5 |
| httpie | 1 | 3 |
| keras | 23 | 20 |
| luigi | 15 | 8 |
| matplotlib | 17 | 9 |
| pandas | 70 | 96 |
| PySnooper | 0 | 2 |
| sanic | 1 | 2 |
| scrapy | 10 | 15 |
| spacy | 3 | 5 |
| thefuck | 10 | 11 |
| tornado | 2 | 6 |
| tqdm | 1 | 4 |
| youtube-dl | 21 | 13 |
| **Total** | **199** | **219** |

### Pull requests

`amazon-ion/ion-python#448`: **recusado** pelo critério de função única. A correção espalha um gerenciador de contexto novo (`_translate_recursion_error`) por várias funções de `simpleion.py`. Ele fica registrado como **caso de controle**: o bug é um estouro do limite de recursão do Python (`RecursionError` em vez de `IonException`), comportamento que está fora do modelo do ESBMC-Python e que, portanto, não se espera que a verificação confirme.

## Verificação de consistência

Checagem feita nos 200 aceitos (não só na amostra de 10 pedida): a função existe no `.buggy.py`, as `removed_lines` estão dentro dela e a mesma função difere no `.fixed.py`. Problemas encontrados:

- `bip_pandas_5`: **inconsistente**. O arquivo no `buggy_commit` informado pelo BugsInPy já contém a correção; `.buggy.py` e `.fixed.py` são idênticos. Foi movido para `bugsinpy_rejected.json`.
- `bip_black_3`: a mudança fica no argumento de um decorador `@click.option` de `main` (`exists=False` para `exists=True`), não no corpo da função. É um erro de configuração de CLI, pouco provável de ser verificável.
- 26 candidatos são correções de pura inserção (`removed_lines` vazio): o fix só adiciona código, então não há linha suspeita pronta no arquivo com bug.

## Ressalvas

- **Categoria do bug e expressão suspeita NÃO foram atribuídas.** O campo `removed_lines` vem direto do patch e indica onde a correção mexeu, não qual expressão causa a falha. A classificação nas categorias do pipeline (divisão por zero, índice fora dos limites etc.) ainda precisa ser feita.
- Aceitar aqui só significa "bug validado pelos mantenedores e localizado em uma função". Muitos candidatos (bugs de lógica de negócio, formatação, APIs externas) não terão categoria compatível com o ESBMC-Python.
- Antes de entrar em `dataset/v2_real_world/`, cada candidato precisa passar pelos mesmos portões de auditoria do dataset atual: `scripts/build_v2_eligible.py`, o registro em `eligibility.json` e os portões executáveis (build e pytest do teste que falha).

## Arquivos

- `bugsinpy_candidates.json` / `bugsinpy_rejected.json`: aceitos com proveniência completa e recusados com motivo.
- `prs_candidates.json` / `prs_rejected.json`: idem para pull requests.
- `sources/<id>.buggy.py` e `sources/<id>.fixed.py`: arquivo completo antes e depois da correção.
- `pr_sources.json`: lista manual de PRs a coletar.

Para refazer a coleta:

```
python scripts/collect_validated_bugs.py bugsinpy
python scripts/collect_validated_bugs.py prs dataset/v2_candidates/pr_sources.json
```
