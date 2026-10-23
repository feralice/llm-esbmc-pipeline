# Passo 2 do item 6: piloto manual em 19 bugs travados (16/10/2026)

Bugs: os 20 da seção 4 de `auditoria_semana1_2026-10-16.md`, menos ip_real_17 (o ESBMC v8.6 já confirma
sozinho). Quatro agentes destravaram à mão, um obstáculo por vez, só em cópias do programa, consultando os
testes de regressão do ESBMC (`regression/python/`) para achar a forma aceita. ESBMC v8.6 com
`--no-pointer-check --no-align-check`. Nenhuma chamada de LLM no pipeline e nenhuma mudança no código.
Material por bug em `artifacts/v2/piloto-manual/<bug>/` (`notes.md`, `result.json`, passos, diffs,
reprodutores e checagem em CPython).

## Resultado

| Final | Bugs |
|---|---|
| ESBMC acusa a exceção na linha do bug e o CPython confirma no original | 13 |
| Desistência (orçamento de obstáculos ou tempo) | 4 (bip_pandas_104, bip_pandas_34, ip_real_11, ip_real_32) |
| Ainda recusado (numpy) | 2 (bip_pandas_33, bip_pandas_7) |

Dos 13, um não passa no controle: em bip_pandas_133 a entrada achada (`axis=3`) também quebra a versão
corrigida; o gatilho real (`axis="index"`) precisaria de `axis` tipado como `str`. Ficam **12**. Ressalvas:
em bip_keras_33, ip_real_16 e bip_scrapy_40 a exceção depende de um stub escrito à mão com a semântica da
biblioteca; em bip_keras_33 a violação só apareceu com `--no-unwinding-assertions` (uma violação achada é
um caminho real; só o SUCCESSFUL fica sem garantia). Uma versão automática deve marcar esses casos como
"confirmado sob modelo".

## Obstáculos

84 obstáculos nos 19 bugs, **4,4 por bug**: o primeiro erro esconde de 3 a 7 outros. Por origem: frontend
do ESBMC 35, harness do pipeline 23, modelos do ESBMC 17, limite de laço 6, dependência 3.

Agrupados pela **correção** que destravou (um bug costuma precisar de 2 a 4 grupos):

| Correção | Bugs em que foi necessária | Automatizável no pipeline |
|---|---|---|
| A. Recorte pelo caminho do bug: tirar métodos e código que o caminho da entrada até a linha suspeita não visita (corpos trocados por `raise NotImplementedError` mantendo as linhas), dobrar guardas de versão mortas (`sys.version_info < (3,)`, `TYPE_CHECKING`), não deixar chamador de método removido | 10 (av_real_03, bip_keras_33, bip_luigi_21, bip_pandas_104, bip_pandas_133, bip_pandas_33, bip_scrapy_40, bip_youtube_dl_30, ip_real_14, ip_real_32) | sim |
| B. Erros do próprio harness: `none=None` gerado no lugar do nome do parâmetro (`render.py`), anotação em texto de import só de `TYPE_CHECKING` (`"DataFrame"`, `"Report"`), atributos que o spec do LLM declarou e o harness descartou (`self.index`, `_AXIS_*`) | 5 (av_real_03, bip_black_16, bip_luigi_21, bip_pandas_133, ip_real_16) | sim |
| C. Stubs com a semântica da biblioteca: alias de builtin (`compat_chr` é `chr`), stdlib real no lugar de valor livre (`math.ceil`), hierarquia de classes preservada, `__call__`/`__getitem__` em stubs usados assim, stub que levanta a exceção da biblioteca (`to_bytes`, `maketrans`, pathlib) | 9 (bip_black_16, bip_keras_23, bip_keras_33, bip_pandas_104, bip_pandas_160, bip_scrapy_40, ip_real_07, ip_real_14, ip_real_16) | em parte (aliases e stdlib sim; semântica de biblioteca exige modelo) |
| D. Reescritas mecânicas para o frontend: anotar o resultado de uma chamada, achatar `a.b.m()` em temporário, nome novo quando a variável muda de tipo, `yield from` como `for`, `async` sem `await` removido, De Morgan, `len()` antes de `str * n`, conversões aninhadas separadas, default `lambda` fora do `get` | 11 | sim, mas cada uma é uma regra pequena; candidatas a regra com sonda |
| E. Limite de laço maior (`--unwind 16` a `20`) | 3 (av_real_03, bip_pandas_160, bip_keras_33) | sim |

## Falsos vereditos do ESBMC v8.6 (sem mensagem de erro)

Achados no piloto, cada um com reprodutor de até 15 linhas na pasta do bug. Afetam a leitura de SUCCESSFUL e
de violações, por isso o replay em CPython continua decisivo:
- exceção perdida numa cadeia de métodos (`r.rel().posix()`), método inexistente em `str` dentro de cadeia e
  `from typing import Any` escondendo a exceção (bip_black_16);
- `hasattr` em variável de laço sempre falso e método inexistente em atributo aninhado sem exceção
  (bip_pandas_160);
- `a[mask] = v` não aplicado (bip_pandas_33); `datetime(..., 24, ...)` aceito e `'|'.join(dict)` com texto
  errado (ip_real_32);
- `list /= float` sem `TypeError` (bip_keras_25); `not (a and b and c)` com `str` avaliado errado,
  `str.partition` em parâmetro devolvendo partes vazias (ip_real_11); `chr(0xD800)` acusado como erro
  (ip_real_07); grupo de `re` livre salvo para o padrão `(\d+)` (ip_real_07).

Limitações do frontend com reprodutor: `*args`/`**kwargs` usados dentro de método (função solta aceita
`*args`, `github_6741_starred`), closure devolvida por método, função aninhada que não vê classe do módulo,
atributo em objeto função, `Core(**d)` derrubando o conversor, `split` só com separador constante,
`str * len(x)`, classe com `__new__`, `async def`. Material para issues ao Lucas.

## Defeito de ferramenta achado

A lista de hipóteses do piloto tinha ids repetidos, e dois pedaços de `v2_replay_specs.py` gravaram no mesmo
arquivo de programa. O resultado "bip_pandas_33 aceito na v8.6" (seção 5 da auditoria) não se sustenta: o
arquivo em disco é do outro pedaço, que é recusado.

## Escolha para a semana 3

Critério: ganho por dia, só o que é do pipeline e não depende de LLM.
- **Intervenção 1: recorte pelo caminho do bug (A).** Uma regra só, presente em 10 dos 19.
- **Intervenção 2: corrigir os erros do harness e os stubs triviais (B e a parte automatizável de C:
  aliases de builtin, stdlib real, parâmetros tipados, sem chamador órfão).** Barata e presente em 5 + vários
  de C.
- Ficam para depois: D (cada reescrita vira regra com sonda, pela skill `/nova-regra`), C semântico (modelos
  de biblioteca) e as falhas do ESBMC (issues).
- Medição: os 19 do piloto mais os 9 de reserva, que não foram olhados, com os specs gravados e sem LLM.
  Como cada bug precisou de 2 a 4 grupos, A e B sozinhas não devem destravar os 12; o que importa é medir
  quantos passam a chegar ao ESBMC e quantos confirmam.

## Resultado da semana 3 (17/10)

As regras R1 a R7 (`docs/desenho/specs/2026-10-17-recorte-e-harness-design.md`), medidas nos 29 bugs com os
specs gravados: veredito do ESBMC 7 → 8, 4 bugs avançam um obstáculo, nenhuma confirmação nova e nenhuma
perda. Confirma a leitura do piloto: com 2 a 4 grupos de correção por bug, duas intervenções isoladas movem
os bugs para o obstáculo seguinte, não até a confirmação. O próximo ganho exige o grupo D (reescritas para o
frontend) e stubs com a semântica da biblioteca, ou a correção do frontend no próprio ESBMC.
