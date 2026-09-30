# Datasets

Mapa de todas as pastas de `dataset/`, do que o pipeline atual usa ao que é só histórico ou está
separado. Os nomes das pastas não mudam porque o código, os testes e os artefatos de rodadas
anteriores apontam para eles.

## Visão geral

| Pasta | O que é | Quem usa | Situação |
|---|---|---|---|
| `v2_real_world/` | **dataset principal**: 116 bugs reais de 42 projetos Python | pipeline V2 (motor verify) | ativo |
| `v2_real_world_eligible/` | subconjunto de 18 bugs cujo harness escrito à mão o ESBMC verifica | baseline manual, opcional | gerado por `scripts/build_v2_eligible.py`; não editar à mão |
| `v2_candidates/` | 199 bugs do BugsInPy validados pelos mantenedores, ainda fora do dataset | teste das regras do harness em código novo | aguardando decisão de inclusão |
| `labeled/` | dataset V1: 70 funções sintéticas, 1 bug ou nenhum por arquivo | benchmark V1 (baseline) | congelado |
| `code_smell/` | 379 trechos com code smells rotulados por humanos (3 fontes externas) | nenhum fluxo ainda; smell não vai para o ESBMC | separado, aguardando decisão |
| `disciplina_pgene601/` | corpus da disciplina PGENE601 (Python ciber-físico) | projeto da disciplina | em triagem (só a decisão de mineração) |

## `v2_real_world/`: qual pasta cada etapa lê

| Pasta ou arquivo | Conteúdo | Etapa |
|---|---|---|
| `detection/` | só a função com bug (116 arquivos) | a LLM lê para apontar o bug (104 entram na métrica) |
| `detection_full/` | arquivo completo do projeto no commit com bug (99) | o recorte tira a função daqui para o ESBMC (`--verification-sources`) |
| `fixed_full/` | arquivo completo no commit da correção (98) | controle: onde não há bug, toda confirmação seria falsa |
| `ground_truths.json`, `manifest.json` | gabarito (função, expressão, categoria) e proveniência (projeto, commits) | só na avaliação |
| `manifest_full.json` | manifesto usado para baixar `detection_full/` e `fixed_full/` | scripts `fetch_v2_*` |
| `eligibility.json`, `esbmc_audit*.json` | portões de verificabilidade dos harnesses de referência | `build_v2_eligible.py` |
| `bugs/` | harness de referência escrito à mão (dataset de 09/09) | **legado**: o motor novo não usa |
| `patches/` | patch real da correção de cada bug | consulta e auditoria |

Os 12 bugs fora da métrica de detecção estão em `manifest.json`, campo
`evaluation_policy.patch_context_items`: só se percebem vendo a correção (ex.: uma constante errada).
