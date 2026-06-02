# Dataset Provenance

All examples are extracted or directly adapted from real open-source projects.
Each file preserves the essential bug pattern from the original source.

---

## Bugs formais

### division_by_zero

| Arquivo | Projeto | Fonte | Bug original | Fix aplicado |
|---|---|---|---|---|
| `pandas_73_division_by_zero.py` | pandas | BugsInPy pandas #73 | `value / divisor` em agregação groupby quando grupo está vazio | Guard de zero na path de agregação |
| `aws_neuron_bilinear_chunk_size_div_zero.py` | aws-neuron/nki-samples | GitHub issue #125 / PR #126 | `(h_src - wdw_size) / step_size` quando `chunk_size == 1` faz `step_size = 0` | `assert chunk_size > 1` antes de calcular step |
| `matplotlib_30_division_by_zero.py` | matplotlib | BugsInPy matplotlib #30 (`lib/matplotlib/colors.py`) | `(xind_i - x_ind_prev) / (x_ind - x_ind_prev)` quando dois pontos de controle do colormap coincidem | Deduplicação de pontos antes do cálculo |
| `tqdm_9_division_by_zero.py` | tqdm | BugsInPy tqdm #9 (`tqdm/_tqdm.py`) | `n / elapsed` na função `format_meter` quando `elapsed == 0.0` no início da iteração | Guard: `rate = n / elapsed if elapsed else None` |
| `httpie_download_division_by_zero.py` | httpie | httpie/downloads.py | `downloaded / total_size * 100` quando servidor não envia `Content-Length` (total_size == 0) | Guard: `if self.total_size else 0` |

### out_of_bounds

| Arquivo | Projeto | Fonte | Bug original | Fix aplicado |
|---|---|---|---|---|
| `scrapy_18_out_of_bounds.py` | scrapy | BugsInPy scrapy #18 (`scrapy/http/headers.py`) | `content_disposition.split(';')[1]` quando header não tem ponto-e-vírgula | Guard `len(parts) > 1` antes do índice |
| `thefuck_9_out_of_bounds.py` | thefuck | BugsInPy thefuck #9 (`thefuck/rules/git_push.py`) | `script_parts.pop(upstream_option_index)` com índice inválido | Validação via `try/except` no `index()` |
| `keras_38_out_of_bounds.py` | keras | BugsInPy keras #38 (`keras/layers/recurrent.py`) | `input_shape[0]` quando `input_shape` é tupla vazia | Validação do comprimento antes do acesso |
| `black_17_out_of_bounds.py` | black | BugsInPy black #17 (`black.py`) | `src_txt[-1]` levanta `IndexError` quando `src_txt == ""` | Alterado para `src_txt[-1:] != "\n"` (slice nunca levanta) |
| `thefuck_1_out_of_bounds.py` | thefuck | BugsInPy thefuck #1 (`thefuck/rules/pip_unknown_command.py`) | `re.findall(...)[0]` levanta `IndexError` quando regex não tem match | Regex ampliado para cobrir mais formatos de nome |

### assertion_violation

| Arquivo | Projeto | Fonte | Bug original | Fix aplicado |
|---|---|---|---|---|
| `black_23_assertion_violation.py` | black | BugsInPy black #23 (`black.py`) | `raise AssertionError("cannot parse source")` quando lib2to3 falha ao parsear | Contexto de exceção corrigido para expor o erro original |
| `pandas_42_assertion_violation.py` | pandas | BugsInPy pandas #42 (`pandas/core/dtypes/common.py`) | `assert left_is_interval and right_is_interval` falha quando apenas um lado é IntervalDtype | Lógica de comparação reescrita para tratar casos mistos |
| `tornado_1_assertion_violation.py` | tornado | BugsInPy tornado #1 (`tornado/websocket.py`) | `assert stream is not None` dispara após WebSocket ser fechado | Alterado para `assert self.ws_connection is not None` |
| `keras_30_assertion_violation.py` | keras | BugsInPy keras #30 (`keras/engine/training.py`) | `assert x is not None and len(x) > 0` dispara quando generator produz batch None | Verificação de None adicionada explicitamente antes do isinstance |
| `scrapy_21_assertion_violation.py` | scrapy | BugsInPy scrapy #21 (`scrapy/http/request/__init__.py`) | `assert method.upper() in SUPPORTED_METHODS` falha para métodos não-padrão como PATCH | Validação convertida para warning em vez de assertion |

---

## Code smells

### long_method

| Arquivo | Projeto | Origem | Smell |
|---|---|---|---|
| `scrapy_cmdline.py` | scrapy | `scrapy/cmdline.py` — `execute()` | Parsing de args, lookup de comando, configuração, logging e execução em um único corpo de função |
| `tqdm_format_meter.py` | tqdm | `tqdm/_tqdm.py` — `tqdm.format_meter()` | ETA, taxa, unidades, renderização da barra, formato customizado e fallback ASCII/unicode em uma função |
| `black_format_str.py` | black | `black.py` — `black.format_str()` | Detecção de encoding, seleção de gramática, parsing CST, split de linhas e normalização misturados |

### many_parameters

| Arquivo | Projeto | Origem | Smell |
|---|---|---|---|
| `requests_get.py` | requests | `requests/api.py` — `requests.get()` | 8 parâmetros: `url, params, headers, auth, timeout, allow_redirects, verify, stream` |
| `scrapy_request.py` | scrapy | `scrapy/http/request/__init__.py` — `Request.__init__()` | 12 parâmetros: `url, callback, method, headers, body, cookies, meta, encoding, priority, dont_filter, errback, flags` |
| `matplotlib_plot.py` | matplotlib | `matplotlib/axes/_axes.py` — `Axes.plot()` | 13 parâmetros de estilo visual: `fmt, color, linestyle, linewidth, marker, markersize, label, alpha, zorder, visible, animated` + 2 dados |

### complex_conditional

| Arquivo | Projeto | Origem | Smell |
|---|---|---|---|
| `thefuck_match.py` | thefuck | `thefuck/rules/git_push.py` — `match()` | 5 ramos elif combinando verificação de script com padrões específicos de stderr |
| `scrapy_middleware.py` | scrapy | `scrapy/downloadermiddlewares/retry.py` — `RetryMiddleware.should_retry()` | 6 ramos: status HTTP, tipo de exceção, contagem de retries e configurações |
| `tornado_routing.py` | tornado | `tornado/web.py` — `RequestHandler.check_xsrf_cookie()` | 5 ramos combinando método HTTP, presença de cookie/header/argumento e versão do token |

---

## Clean (casos negativos)

| Arquivo | Descrição |
|---|---|
| `clean_math.py` | Divisão guardada com check explícito de zero — falso positivo esperado |
| `clean_list.py` | Acesso a lista guardado com check de vazio — falso positivo esperado |

---

## Referências dos datasets originais

- **BugsInPy**: Widyasari et al., "BugsInPy: A Database of Existing Bugs in Python Programs to Enable Controlled Testing and Debugging Studies", FSE 2020. https://github.com/soarsmu/BugsInPy
- **AWS Neuron NKI Samples**: https://github.com/aws-neuron/nki-samples (issue #125)
- **requests**: https://github.com/psf/requests
- **matplotlib**: https://github.com/matplotlib/matplotlib
