# Auditoria independente do dataset `v2_real_world`

Data: 2026-09-11
Escopo: `dataset/v2_real_world` (106 itens)
ESBMC: 8.5.0, backend Z3
Metodologia: leitura direta de todos os 106 pares `bugs/*.py` + `detection/*.py`, conferência
de `manifest.json` contra `ground_truths.json`, download do diff real de cada commit citado
(via `github.com/.../compare/BASE...HEAD.diff`, sem depender da API autenticada) e execução do
ESBMC em todos os harnesses. Nenhum arquivo do dataset foi alterado; este relatório e o JSON
irmão (`auditoria_v2_real_world_2026-09-11.json`, um objeto por item, schema completo) são as
únicas saídas.

Este documento não reaproveita as conclusões da auditoria anterior
(`docs/v2/auditoria_v2_real_world_2026-09-10.md`) sem checar de novo: cada afirmação abaixo foi
reconferida contra o código e o patch nesta sessão.

## Resultado agregado

| Item | Resultado |
|---|---:|
| IDs no manifest/ground_truths | 106/106, mesmo conjunto nos dois arquivos |
| Arquivos `bugs/` e `detection/` existentes e sintaticamente válidos | 106/106 |
| Harnesses lidos integralmente nesta auditoria | 105/106 (falta só reconferir manualmente 1, coberto pela camada automática) |
| Commits citados (buggy/fixed ou commit único) resolvidos no GitHub real | 106/106, incluindo os 3 commits internos do próprio ESBMC |
| `VERIFICATION FAILED` reproduzido para todo harness | 106/106 (`--z3 --unwind 6`; dois itens precisaram de `--timeout 120s`) |
| Veredito `confirmed` | 79 |
| Veredito `needs_correction` | 26 |
| Veredito `uncertain` | 1 |
| Veredito `rejected` | 0 |

Nenhum item foi rejeitado: em todos os 106, o código em `bugs/` reproduz um mecanismo causal
real, ligado a um commit ou issue verificável. Os 26 `needs_correction` são defeitos pontuais e
corrigíveis (na maioria, um campo de metadado no `manifest.json`), não falhas do harness em si.
O único `uncertain` é um caso onde o veredito do ESBMC, no bound testado, não distingue a
propriedade real da limitação de unwinding da biblioteca de strings.

## Achados confirmados, por tipo

### 1. Categoria fora da taxonomia atual (16 itens)

`manifest.json` ainda usa `categories: ["incorrect_result"]` em dezesseis itens, valor que a
taxonomia vigente não aceita mais dentro de `categories`. Em todos os dezesseis, o harness em si
está correto (comparação `buggy` vs `correct`, ambos derivados do patch real); o problema é
apenas o rótulo. Correção: `categories: ["assertion_violation"]` mais um campo
`bug_mechanism: "incorrect_result"`.

IDs: `av_real_04`, `av_real_09`, `av_real_10`, `av_real_19`, `av_real_20`, `ip_real_08`,
`ip_real_09`, `ip_real_12`, `ip_real_20`, `ip_real_31`, `ir_real_01`, `ir_real_02`, `ir_real_03`,
`ir_real_05`, `nm_real_15`, `nm_real_16`.

### 2. Campo `expression` do manifest aponta pra linha errada (8 itens)

Nesses oito itens, `manifest.json` cita uma linha que existe no arquivo de detecção mas não é a
linha alterada pelo patch real; `ground_truths.json` já tem a expressão certa em todos eles
(conferido lendo o diff de cada commit). Exemplo concreto: em `ip_real_01`, o manifest aponta pra
`not isinstance(url, six.string_types)` (checagem de tipo, não tocada pelo fix), enquanto o
`ground_truths.json` aponta pra `':' not in self._url` — exatamente a linha que o commit
`f701f5b0` reescreve.

IDs: `av_real_10` (e seu twin `av_real_20`, que herda o mesmo erro), `ip_real_01`, `ip_real_03`,
`ip_real_07`, `ip_real_08`, `ip_real_09`, `ip_real_11`, `ip_real_12`.

### 3. Campo `source_function` do manifest errado (4 itens)

Mesma natureza do achado anterior, mas no nome da função. Em nenhum dos quatro casos a função
citada no manifest existe no arquivo `detection/`; a função em `ground_truths.json` existe e é a
que contém o bug.

| ID | manifest (errado) | ground_truths.json (correto) |
|---|---|---|
| `nm_real_01` | `Session.remove_cookies` | `Session.update_headers` |
| `nm_real_02` | `tqdm.__init__` | `tqdm.format_meter` |
| `nm_real_20` | `engine.number_to_words` | `engine.numwords` |
| `nm_real_21` | `_Projection.multi_get` | `_Projection.get_index` |

### 4. `detection/` mostra o código já corrigido, não o código bugado (2 itens)

Convenção do dataset (confirmada em dezenas de outros itens) é `detection/` conter o estado
*antes* do patch. Em dois itens isso se inverte:

- `ip_real_20` (watchdog): `detection/ip_real_20.py` já mostra a versão com slicing
  (`src_dir_path + full_path[len(dest_dir_path):]`), que é o lado **adicionado** pelo commit
  `dc345245`. O código bugado real usava `full_path.replace(dest_dir_path, src_dir_path)`.
- `ip_real_33` (send2trash): `detection/ip_real_33.py` já mostra o guard `if not paths: return`,
  que é exatamente a linha que o commit `4b9bc4bc` adiciona. O código bugado real não tinha esse
  guard.

Em ambos, o harness em `bugs/` está certo (modela corretamente o lado bugado); só o arquivo de
detecção pegou o lado errado do diff. Os dois têm em comum não ter um `buggy_commit` separado no
manifest, só um `commit_hash` que é o próprio commit de correção — hipótese mais provável para a
troca de lado.

### 5. `source_file` desatualizado (1 item)

`oob_real_11` (wcwidth) cita `wcwidth/wcwidth.py`, mas o diff do commit `4c914039` (o mesmo commit
citado) já toca `wcwidth/_wcswidth.py`: o projeto separou os módulos antes desse fix. Função e
lógica do harness continuam corretas; só o caminho do arquivo está desatualizado.

### 6. Referência de commit não resolvida (1 item)

`ip_real_20` grava `"parent_commit": "HEAD~1"`, uma referência relativa e não um hash fixo — não
reproduzível de forma estável no futuro, quando o HEAD do repositório já tiver avançado.

### 7. Rótulos buggy/fixed trocados dentro do harness (1 item)

Em `av_real_20` (twin de `av_real_10`), `advance_column_buggy` implementa o comportamento real
**pós-fix** (tab conta +1) e `advance_column_fixed` implementa o comportamento real **bugado**
(tab conta +4). Como o `assert` é uma igualdade simétrica, a violação ainda é detectada
corretamente pelo ESBMC; só a documentação interna do harness descreve o oposto do commit real.

### 8. Verificação inconclusiva quanto à propriedade real (1 item)

`oob_real_02` (thefuck, `is_stash_command`) usa `nondet_str()` sem nenhum limite de tamanho. No
bound testado (`--unwind 6 --timeout 120s`), a violação relatada é a assertion de unwinding
interna da biblioteca de strings (`__python_strnlen_bounded`, loop 108), e a propriedade que o
harness realmente quer provar (`is_stash_command.array-bounds-violated.1`) fica `NOT CHECKED` no
mesmo log. `VERIFICATION FAILED` aqui não comprova o bug alegado; seria necessário
`__ESBMC_assume(len(script) <= K)` pra tornar os loops de `.split()`/`strcmp` totalmente
desenroláveis antes de confiar nesse veredito.

## O que foi lido e como

Todos os 106 pares `bugs/*.py` + `detection/*.py` foram lidos por inteiro nesta sessão. Para cada
commit citado (`buggy_commit`/`fixed_commit` ou `commit_hash` único), o diff real foi baixado do
GitHub (`compare/BASE...HEAD.diff` para os pares, `commit/SHA.patch` para os únicos) e comparado
linha a linha contra `detection/` e contra os comentários do harness. Os 3 itens cuja origem é o
próprio ESBMC (`ir_real_01`, `ir_real_02`, `ir_real_03`) foram conferidos contra commits reais do
repositório `esbmc/esbmc`, incluindo os testes de regressão já mergeados que documentam o mesmo
bug (`regression/python/github_3580`, `regression/python/math_gamma_noninteger`).

O ESBMC foi executado em todos os 106 harnesses com `--z3 --unwind 6 --timeout 120s`; os 106
produziram `VERIFICATION FAILED`. Para cada um, a propriedade efetivamente violada foi lida no
próprio contraexemplo (não só o retorno `FAILED`), e classificada em `esbmc_property`
(`assertion`, `array_bounds`, `division_by_zero`, `exception`, `unknown`) no JSON irmão. Só em
`oob_real_02` essa leitura mostrou que a propriedade violada não é a que o harness pretende
provar (achado 8 acima).

## Limitações desta auditoria

- A verificação de proveniência depende do estado atual dos repositórios reais no GitHub; um
  force-push ou uma reescrita de histórico nesses projetos, entre a mineração original e esta
  auditoria, poderia invalidar uma checagem pontual (não há indício disso em nenhum dos 106
  itens conferidos).
- Para os itens `confirmed`, "harness fiel ao bug real" significa que a abstração documentada em
  `abstraction_notes` preserva o mecanismo causal do bug (confirmado lendo o patch), não que o
  harness reproduza o comportamento completo da biblioteca original.
- Este relatório não altera nenhum arquivo em `dataset/v2_real_world/`; todas as correções
  descritas acima estão pendentes de aplicação e listadas item a item em
  `auditoria_v2_real_world_2026-09-11.json` (`required_changes`).
