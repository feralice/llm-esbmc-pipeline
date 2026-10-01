# Datasets

## Três palavras que confundem

- **Bug validado:** o bug existe de verdade, porque o próprio projeto o corrigiu num commit oficial.
  No BugsInPy há ainda um teste que falha antes da correção. Não depende do ESBMC.
- **Harness:** o programa que o ESBMC executa para testar uma função. Hoje o pipeline gera o harness
  sozinho a cada rodada, e ele não fica salvo no dataset. Os harnesses de `v2_real_world/bugs/`
  foram escritos à mão em 09/09, antes do pipeline atual.
- **V1 e V2:** a V1 usou 70 funções **sintéticas**, escritas para o experimento; a V2 usa **bugs
  reais** de projetos Python. O pipeline atual é a V2.

## Mapa

| Pasta | O que é | Versão | Bug validado? | O pipeline usa hoje? |
|---|---|---|---|---|
| `v2_real_world/` | **dataset principal**: 116 bugs reais de 42 projetos | V2 | sim | **sim** |
| `v2_candidates/` | 199 bugs do BugsInPy para aumentar o principal | V2, próximo passo | sim | ainda não |
| `labeled/` | 70 funções sintéticas da V1 (bugs, funções limpas e code smells) | V1 | não se aplica (sintético) | só no benchmark V1 |
| `code_smell/` | 379 trechos com code smells rotulados por humanos (3 fontes externas) | nenhuma | rótulo humano | não |
| `disciplina_pgene601/` | corpus da disciplina PGENE601 (Python ciber-físico), em triagem | nenhuma | ainda não | não |
| `historico/` | o que não se usa mais, guardado para reprodução | V2 antiga | sim | não |

## `v2_real_world/`: o dataset principal

| Pasta ou arquivo | Conteúdo | Quem lê |
|---|---|---|
| `detection/` | só a função com bug, um arquivo por bug (116) | a LLM, para apontar o bug |
| `detection_full/` | o arquivo completo do projeto no commit com bug (99) | o pipeline, para montar o harness |
| `fixed_full/` | o arquivo completo no commit da correção (98) | o controle: ali qualquer confirmação seria falsa |
| `ground_truths.json` | gabarito: função, expressão e categoria de cada bug | só a avaliação |
| `manifest.json`, `manifest_full.json` | de onde veio cada bug (projeto, commits) e como baixar os arquivos completos | a avaliação e os scripts `fetch_v2_*` |
| `patches/` | o patch oficial da correção de cada bug | consulta e auditoria |
| `bugs/` | harnesses escritos à mão em 09/09, com bug e corrigidos | o avaliador usa os nomes desses arquivos; o pipeline atual **não** usa os harnesses |
| `eligibility.json`, `esbmc_audit*.json` | quais harnesses manuais o ESBMC conseguia rodar | `scripts/build_v2_eligible.py` |

De onde vêm os 116 bugs: 85 do BugsInPy (correção oficial e teste que falha antes dela) e 31 de
commits de correção no histórico dos próprios projetos. 17 não têm `detection_full/`, porque o trecho
de `detection/` foi recortado à mão e não coincide com o arquivo original; nesses casos o pipeline
usa o trecho, que não traz os imports.

Os 12 bugs fora da métrica de detecção estão em `manifest.json`, campo
`evaluation_policy.patch_context_items`: só se percebem vendo a correção (ex.: uma constante errada).

## `v2_candidates/`: para aumentar o dataset

Bugs do BugsInPy que passaram nos critérios de `v2_candidates/README.md`: correção comprovada por
teste, um só arquivo e uma só função alterados. Nada aqui entra nas métricas até ser promovido para
`v2_real_world/`.

## `historico/`

| Pasta | O que é | Como recriar |
|---|---|---|
| `v2_real_world_eligible/` | os 18 bugs cujo harness manual o ESBMC rodava (09/09) | `python3 scripts/build_v2_eligible.py` |

## Regra para o que vem depois

- Bug novo entra primeiro em `v2_candidates/` e só passa para `v2_real_world/` com `detection/`,
  `detection_full/`, `fixed_full/`, patch e entrada no gabarito.
- Nenhum harness escrito à mão: o pipeline gera o harness (níveis 1 e 2) a cada rodada.
