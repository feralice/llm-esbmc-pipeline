# Auditoria de proveniência do gabarito v2_real_world

Data: 2026-09-08. Escopo: todos os itens de `dataset/v2_real_world/ground_truths.json` cujo `provenance` traz `buggy_commit` E `fixed_commit` preenchidos.

**Nota sobre a contagem.** A tarefa original falava em 41 itens. A contagem real no JSON é **40** itens com os dois campos de commit preenchidos (mais um caso à parte, `tm_real_03`, que tem só `buggy_commit` e `fixed_commit` nulo, portanto fora do critério pedido e não auditado aqui). Os números abaixo somam 40, não 41.

Cada item foi checado contra (a) o arquivo real de detecção em `dataset/v2_real_world/detection/<id>.py`, o que a LLM efetivamente recebe, e (b) o diff real do commit de correção no GitHub (via WebFetch, complementado por leitura do arquivo do commit-pai quando necessário). Quando a checagem de commit/detecção não bastou pra decidir, o harness em `dataset/v2_real_world/bugs/<id>.py` também foi lido.

## Resumo numérico (40 itens no total)

| Classificação | Quantidade |
|---|---|
| CONFIRMADO | 30 |
| INCONSISTÊNCIA_INTERNA | 8 |
| FUNÇÃO_ERRADA_NA_DETECÇÃO | 2 |
| NÃO_LOCALIZADO | 0 |

Dos 30 confirmados, 3 vêm da checagem anterior desta sessão (`dz_real_01`, `ip_real_18`, `nm_real_13`); os outros 27 foram checados agora. Um dos dois casos de função errada (`ip_real_04`) também vem da checagem anterior; o outro (`vm_real_01`) foi achado nesta rodada.

## Tabela completa

| id | projeto | classificação | evidência |
|---|---|---|---|
| dz_real_01 | (checado antes) | CONFIRMADO | Função/expressão/bug batem com o diff real do commit de correção (verificado na sessão anterior). |
| ip_real_18 | (checado antes) | CONFIRMADO | Função/expressão/bug batem com o diff real do commit de correção (verificado na sessão anterior). |
| nm_real_13 | (checado antes) | CONFIRMADO | Função/expressão/bug batem com o diff real do commit de correção (verificado na sessão anterior). |
| ip_real_04 | tornado | FUNÇÃO_ERRADA_NA_DETECÇÃO | O campo de topo aponta `HTTP1Connection._read_body`, que já checa `"chunked"` corretamente no arquivo de detecção; o bug real (checagem de `"chunked"` ausente) mora em `write_headers`, função que não existe no arquivo de detecção. |
| av_real_06 | thefuck | CONFIRMADO | Commit `1285303`: antes `return '{} --staged'.format(command.script)`, depois `command.script.replace(' diff', ' diff --staged')`. A expressão de topo bate literalmente com a linha pré-fix mostrada em `detection/av_real_06.py`. |
| av_real_07 | thefuck | CONFIRMADO | Commit `25cc98a`: antes `'ls' in command.script and not ('ls -' in command.script)`, exatamente a expressão de topo e o conteúdo de `detection/av_real_07.py`. |
| av_real_08 | thefuck | CONFIRMADO | Commit `88831c4` inverte a ordem do merge (`dict(kwargs); conf.update(self)` no lugar de `dict(self); conf.update(kwargs)`), confirmando a nota de abstração de que kwargs vence indevidamente antes do fix; a expressão de topo `conf.update(kwargs)` está na linha certa. |
| av_real_09 | matplotlib | CONFIRMADO | Commit `407a9fe` troca `max(vmin,vmax,oldmax), min(vmin,vmax,oldmin)` por `max(...,oldmin), min(...,oldmax)`; a expressão de topo é cópia literal da linha pré-fix, presente no `else` do arquivo de detecção. |
| av_real_10 | black | INCONSISTÊNCIA_INTERNA | Commit `66aa676` mostra que o código pré-fix tratava tab como `+4` e espaço como `+1` (diferenciados), e o fix unifica os dois em `+1`. O harness do item (`bugs/av_real_10.py`) inverte essa lógica: chama de "buggy" a versão tab=+1 (que é na verdade o código já corrigido) e de "correct" a versão tab=+4 (que é o bug real). Abstraction_notes descreve a mesma inversão, então o erro é interno e consistente dentro do item, só que de cabeça pra baixo em relação ao commit real. |
| av_real_11 | tornado | CONFIRMADO | Commit `1131c9b`: antes `headers.get("Transfer-Encoding") == "chunked"`, depois com `.lower()`. Bate com a expressão de topo e com `detection/av_real_11.py`. |
| ip_real_01 | scrapy | INCONSISTÊNCIA_INTERNA | O campo `expression` de topo cita `not isinstance(url, six.string_types)`, um check de tipo não relacionado ao bug. O commit real (`f701f5b`) mostra que o bug é `':' not in self._url` virando `('://' not in url) and (not url.startswith('data:'))`; é exatamente isso que `abstraction_notes` e o harness (`has_colon`/`has_dslash`/`starts_data`) modelam corretamente, mas o campo de topo aponta para outro trecho da mesma função. |
| ip_real_03 | scrapy | INCONSISTÊNCIA_INTERNA | `expression` de topo é `"text is not None"`, uma linha pré-existente sem relação com o bug. O commit real (`2c9a38d`) adiciona um `raise ValueError` quando `response` e `text` são passados juntos; é isso que `abstraction_notes` e o harness (`buggy_init_raises`/`correct_init_raises`) capturam certo, mas o campo de topo mira noutra linha da função. |
| ip_real_05 | ansible | CONFIRMADO | Commit `5b9418c`: `__gt__` pré-fix é `not self.__lt__(other)`, igual à expressão de topo, e o harness (`a >= b` vs `a > b`) reproduz o efeito de "maior ou igual" tratado como "maior". |
| ip_real_06 | pandas | CONFIRMADO | Commit `e7ee418` corrige `clocs = [v if i > v else v - 1 for v in clocs]` para usar `val` em vez do índice de laço obsoleto `i`; o harness (`buggy_elem`/`correct_elem`) reproduz exatamente essa troca de variável, mesmo com a expressão de topo (`"clocs"`) sendo pouco específica. |
| ip_real_07 | youtube-dl | INCONSISTÊNCIA_INTERNA | `expression` de topo é `compat_html_entities.name2codepoint`, o lookup de entidades nomeadas, sem relação com o bug. O commit real (`7aefc49`) envolve exceção não tratada em `compat_chr(int(numstr, base))` para entidades numéricas fora do range Unicode; é isso que o harness (`entity_codepoint`/`chr(codepoint)`) modela certo, mas o campo de topo mira outro trecho da função. |
| ip_real_08 | sanic | INCONSISTÊNCIA_INTERNA | `expression` de topo é a chamada `self.router.find_route_by_view_name(...)`, sem relação com o bug. O commit real (`861e873`) mostra que o host extraído da URI da rota nunca era usado para montar `netloc`; é isso que `abstraction_notes` e o harness (`buggy_netloc`/`correct_netloc`) capturam certo. |
| ip_real_09 | ansible | INCONSISTÊNCIA_INTERNA | `expression` de topo é `"vlan_id" in to_remove`, um guard de early-return não relacionado ao bug. O commit real (`4ec1437`) adiciona `if key in to_set.keys(): continue` no laço de remoção; é isso que o harness (`buggy_emits_removal`/`correct_emits_removal`) modela certo, mas o campo de topo aponta outra linha. |
| ip_real_10 | scrapy | CONFIRMADO | Commit `c3d3a94` inverte a ordem de prioridade em `settings.get('SPIDER_LOADER_CLASS', settings.get('SPIDER_MANAGER_CLASS'))` para `settings.get('SPIDER_MANAGER_CLASS', settings.get('SPIDER_LOADER_CLASS'))`; a expressão de topo cita literalmente uma das duas chamadas, na função certa, e o harness reproduz a troca de prioridade. |
| ip_real_11 | fastapi | INCONSISTÊNCIA_INTERNA | `expression` de topo é a variável `authorization`, sem relação com o bug. O commit real (`d262f6e`) adiciona checagem de `self.auto_error` no branch de esquema inválido, que antes sempre levantava `HTTPException`; é isso que o harness (`check_bearer`, `should_raise == auto_error`) modela certo. |
| ip_real_12 | ansible | INCONSISTÊNCIA_INTERNA | `expression` de topo é `want.get`, uma chamada genérica usada em várias linhas da função. O commit real (`68de182`) remove o `and not needs_update('vrf')` do guard `if needs_update('state') and not needs_update('vrf'):`; é isso que `abstraction_notes` e o harness (`buggy_should_update_state`/`correct_should_update_state`) capturam certo. |
| ip_real_13 | tornado | CONFIRMADO | Commit `db52903` altera exatamente a condição `(start is not None and start >= size) or end == 0`, idêntica à expressão de topo e ao conteúdo de `detection/ip_real_13.py`. |
| ip_real_14 | keras | CONFIRMADO | Commit `5422fdd` adiciona o `+1` faltante em `(self.end_index - self.start_index)`; a expressão de topo cita exatamente esse subtrecho, na função `__len__` correta. |
| ip_real_32 | parse | CONFIRMADO | Commit `4cf2b44` (parente do commit citado como buggy, já corrigido no próprio item via `_correction_note`) adiciona clamp de `H > 23` após `H += 12`; a expressão de topo bate com a linha pré-fix e com `detection/ip_real_32.py`. |
| nm_real_10 | luigi | CONFIRMADO | Commit `8501e5d` muda `if len(self.columns) > 0:` para `if self.columns and len(self.columns) > 0:`; a expressão de topo (`len(self.columns)`) está na linha certa. |
| nm_real_11 | scrapy | CONFIRMADO | Commit `439a3e5` envolve `while len(self) >= self.limit:` com `if self.limit:`; a expressão de topo bate com a linha pré-fix exata. |
| nm_real_12 | ansible | CONFIRMADO | Commit `a4b59d0` adiciona `if current_line.next is not None:` antes de `current_line.next.prev = current_line.prev`; a expressão de topo é literalmente essa linha que passou a precisar do guard. |
| oob_real_04 | thefuck | CONFIRMADO | Commit `e2e8b6f` adiciona `if self._cached:` antes de indexar `self._cached[0]`; a expressão de topo bate com a linha pré-fix e com `detection/oob_real_04.py`. |
| oob_real_05 | black | CONFIRMADO | Commit `7fc6ce9` troca `if src_txt[-1] != "\n":` por `if src_txt[-1:] != "\n":`; a expressão de topo é idêntica à linha pré-fix. |
| tm_real_01 | spacy | CONFIRMADO | Commit `9fa9d7f` estende `head != "0"` para `head not in ["0", "_"]`; a expressão de topo reproduz a linha pré-fix inteira. |
| tm_real_02 | luigi | CONFIRMADO | Commit `e2be971` adiciona `.lower()` em `table in stdout`; a expressão de topo `return stdout and table in stdout` é a linha pré-fix exata. |
| tm_real_04 | youtube-dl | CONFIRMADO | Commit `348c6bf` troca o guard `if int_str is None: return None` por checagem de tipo `isinstance`; a expressão de topo reproduz o guard antigo, e o harness modela a falta do isinstance corretamente. |
| tm_real_05 | scrapy | CONFIRMADO | Commit `ff3aec6` envolve `to`/`cc` em `arg_to_iter(...)` antes de `msg['To'] = COMMASPACE.join(to)`; a expressão de topo é a linha que corrompe o resultado quando `to` é string em vez de lista. |
| tm_real_06 | scrapy | CONFIRMADO | Commit `16dad81` troca a ordem de `failure.value, failure.type, ...` para `failure.type, failure.value, ...`; a expressão de topo é a linha pré-fix idêntica. |
| tm_real_07 | matplotlib | CONFIRMADO | Commit `2a3707d` troca `self._filled = True` fixo por `self._filled = self._fillstyle != 'none'`; a expressão de topo é a linha pré-fix exata, na função `_recache` certa. |
| vm_real_01 | tqdm | FUNÇÃO_ERRADA_NA_DETECÇÃO | O commit real (`cae9d13`) corrige `l_bar, r_bar = l_bar.format(...), r_bar.format(...)` dentro de um bloco `if '{bar}' in bar_format: l_bar_user, r_bar_user = bar_format.split('{bar}')` que só existe no `format_meter` do commit buggy (`08b8ad1`). Esse bloco inteiro está ausente em `detection/vm_real_01.py`: o arquivo mostrado à LLM só tem o branch `else: return bar_format.format(**bar_args)`, sem nunca calcular `l_bar_user`/`r_bar_user`. A LLM não tem como achar esse bug varrendo o arquivo de detecção, mesmo a função tendo o nome certo. |
| io_real_01 | matplotlib | CONFIRMADO | Commit `5d99e15` adiciona `vmin, vmax = map(float, [vmin, vmax])` citando textualmente `abs(np.int8(-128)) == -128` como motivo, igual à nota de abstração do item; a expressão de topo `maxabsvalue = max(abs(vmin), abs(vmax))` é a linha afetada. |
| ir_real_01 | esbmc | CONFIRMADO | Commit `d432ae5` (repositório do próprio ESBMC) remove `pi_const: float = 3.14153` de `gamma`/`lgamma` em favor do `pi` do módulo; a expressão de topo é a linha de retorno pré-fix idêntica. |
| ir_real_02 | esbmc | CONFIRMADO | Mesmo commit da família `2e99e3c` corrige `pi`/`e`/`tau` de valores truncados para dupla precisão; a expressão de topo `pi: float = 3.14153` é a linha pré-fix exata. |
| ir_real_03 | esbmc | CONFIRMADO | Commit `d8ad534` corrige `if pattern_len != 7:` para `!= 6`; a expressão de topo é a linha pré-fix exata, e a nota de abstração cita corretamente o padrão de 6 caracteres afetado. |
| dz_real_04 | nki-samples | CONFIRMADO | Commit `d631c88` adiciona `assert chunk_size >= 2` (e um segundo assert de `h_src >= chunk_size`); a nota de abstração descreve exatamente esse fix e a divisão por `step_size` (`chunk_size - 1`) que zera quando `chunk_size == 1`. |

## Itens que precisam correção

Dez itens (dos 40 auditados) têm um problema real de rótulo que merece edição em `ground_truths.json`. Nada foi alterado no arquivo, essa seção é só o relatório.

### FUNÇÃO_ERRADA_NA_DETECÇÃO (2 itens, o caso mais grave)

- `ip_real_04` (tornado): o arquivo de detecção mostra `HTTP1Connection._read_body`, que já checa `"chunked"` direito; o bug de verdade fica em `write_headers`, ausente do arquivo. A LLM não pode achar esse bug a partir do que recebe.
- `vm_real_01` (tqdm): falta em `detection/vm_real_01.py` o bloco `if '{bar}' in bar_format:` inteiro, onde mora o bug real (`l_bar`/`r_bar` usados no lugar de `l_bar_user`/`r_bar_user`). O arquivo mostrado à LLM nem chega a calcular essas duas variáveis.

### INCONSISTÊNCIA_INTERNA (7 itens com ponteiro errado dentro da mesma função, 1 com lógica invertida)

Sete destes têm o mesmo padrão: o campo `expression` de topo cita uma linha da função correta, mas que não é a linha do bug; enquanto isso, `abstraction_notes` e o harness em `bugs/<id>.py` acertam a linha certa. Corrigir aqui significa só trocar o valor de `expression` (e possivelmente `harness_expression`, quando também genérico) pela linha que o commit real mudou, sem tocar no harness em si, que já está correto:

- `ip_real_01` (scrapy): trocar `not isinstance(url, six.string_types)` pela checagem de esquema (`':' not in self._url` / `'://' not in url and not startswith('data:')`).
- `ip_real_03` (scrapy): trocar `text is not None` pelo `raise ValueError` de mútua exclusão ausente.
- `ip_real_07` (youtube-dl): trocar `compat_html_entities.name2codepoint` pela chamada `compat_chr(int(numstr, base))` sem try/except.
- `ip_real_08` (sanic): trocar a chamada a `find_route_by_view_name` pela linha do `netloc` que ignora o host extraído da URI.
- `ip_real_09` (ansible): trocar `"vlan_id" in to_remove` pelo laço de remoção sem checagem de `to_set`.
- `ip_real_11` (fastapi): trocar a variável `authorization` pela falta de checagem de `self.auto_error` no branch de esquema inválido.
- `ip_real_12` (ansible): trocar `want.get` pela condição `needs_update('state') and not needs_update('vrf')`.

O oitavo é de natureza diferente, não é um ponteiro errado mas uma lógica inteira de cabeça pra baixo:

- `av_real_10` (black): o harness chama de "buggy" a versão que trata tab como espaço (`+1`), quando essa é justamente a versão corrigida pelo commit real; e chama de "correct" a versão que soma `+4` pro tab, que é o comportamento buggy de verdade. Corrigir aqui exige trocar os nomes/corpos de `buggy_column` e `correct_column` em `bugs/av_real_10.py` (e o texto de `abstraction_notes`), não só o campo de topo.
