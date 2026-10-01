# Harness guiado pelo ESBMC (01/10)

Objetivo: o harness não deve recusar nada que o ESBMC consiga verificar, para que o maior número
possível de hipóteses da LLM receba um veredito do ESBMC. O que o ESBMC recusar fica só com o
resultado da LLM.

## O que mudou

| Mudança | Onde | Por quê |
|---|---|---|
| Oráculo: a conversão do ESBMC (`--goto-functions-only`, cerca de 1 s) roda sobre o programa provisório antes da LLM; cada membro de biblioteca que ele não conhece vira stub, o resto do módulo continua real | `verify/oracle.py`, `slicing.stub_imports`, `loop.precheck` | substitui a lista fixa de módulos; `re.sub` virava `assert(false)` e gerava violação falsa |
| Modelos fixos para `threading.RLock` e `threading.local` | `slicing.MEMBER_MODELS` | o driver tem uma thread só, então trava reentrante sempre adquire |
| Tipos `set[T]`, `frozenset[T]` (escalares) e `Optional[None]` | `spec.py`, `render.py`, prompt | o ESBMC 8.5 aceita; o harness recusava |
| Exceções que o ESBMC não modela (`DeprecationWarning`, `SystemExit`, `UnicodeDecodeError`, `WindowsError`...) viram classes com a hierarquia do CPython, só no programa do ESBMC | `render._exception_stubs` | o ESBMC modela 21 das 69 exceções do CPython; a reexecução usa as reais |
| `%` reescrito também para tupla de nomes e para texto comprovadamente `str` exato | `compat.py` | mantém a regra de equivalência exata no CPython (testes de fronteira) |
| Stub cujo resultado é desempacotado (`a, b = lib.f()`) exige `tuple` com o mesmo número de itens | `spec.spec_problems` | erro "Cannot unpack" agora vira retorno claro para a LLM, antes do ESBMC |
| Limite de laço sobe de 5 para 10 e 20 quando o ESBMC só reporta "unwinding assertion" | `loop.verify_hypothesis` | limite curto não prova ausência de bug |
| A reexecução testa primeiro os valores do contraexemplo do ESBMC | `replay.counterexample_seeds`, `replay_worker` | antes só testava `{0, 1, -1, 2}`; um bug com `n = 8` nunca era confirmado |
| Parâmetros de stub todos opcionais | `render._stub_params` | chamadas do mesmo stub com número diferente de argumentos quebravam (`Path() missing 1 required positional argument`) |
| Suposições aceitam `x in ('GET', 'HEAD')` e campos de entradas `object` (`self.cron.RANGES`) | `spec._assumption_problem`, prompt | eram válidas e o ESBMC aceita; o validador recusava |
| `__new__` sai junto com o `__init__` quando o harness gera o estado do receptor | `slicing.prune_class` | `super(C, cls).__new__(cls, **kwargs)` travava o ESBMC sem fazer parte do que se verifica |
| Desempacotar entrada ou campo (`n, c = arr.shape`) exige tupla do mesmo tamanho | `grounding._unpacked_inputs`, `spec_problems` | mesma ideia dos stubs, agora para entradas |
| Em timeout, tenta Boolector e depois Z3 | `loop.verify_hypothesis` | só aceita a nova leitura se for veredito (violação ou seguro) |

## Medição sem custo de API

`scripts/v2_replay_specs.py` reaproveita as especificações gravadas de uma rodada (aqui, a de 30/09)
e passa tudo pelo harness atual e pelo ESBMC. Mesmo binário do pipeline (`/usr/local/bin/esbmc`,
release 8.5), 180 s, 125 hipóteses com a localização dada:

| | harness de 30/09 | harness novo |
|---|---|---|
| com veredito do ESBMC | 11 | 17 |
| confirmados | 2 | 3 |
| timeout | 7 | 5 a 6 (varia com a carga da máquina) |

A confirmação nova é `oob_real_02` (timeout antes; agora o limite maior e a troca de solver chegam ao
contraexemplo, e o CPython reproduz o `IndexError`). Também passaram a ter veredito `av_real_17` (duas
hipóteses, `re.sub` stubado), `tm_real_04`, `ip_real_04`, `ir_real_03` e `ip_real_10`.

Controle nas versões corrigidas (`fixed_full`, modo estrito, 107 hipóteses com arquivo): 0 confirmações.

As especificações gravadas não respondem às mensagens novas do harness (tipos `set`, desempacotamento,
suposições com `in`); esse ganho só aparece numa rodada com a LLM. Comandos:

```
python3 scripts/v2_replay_specs.py artifacts/v2/exp-oracle-repair-cobertura/v2_verify_report.json \
    --esbmc /usr/local/bin/esbmc --timeout 180 --out <saida> [--shard i/n] [--only id1,id2]
python3 scripts/v2_replay_specs.py artifacts/v2/exp-oracle-fixed-cobertura/v2_verify_report.json \
    --esbmc /usr/local/bin/esbmc --sources dataset/v2_real_world/fixed_full --strict-sources --out <saida>
```

## Braço do agente (Claude Code + plugin ESBMC)

`scripts/v2_agent_reverify.py` reavalia os harnesses que o agente salvou em 30/09 (49 casos em que o
motor parava), sem chamar o agente de novo. Com a reexecução usando o contraexemplo do ESBMC e o sandbox
bloqueando só introspecção (não mais `__len__`, `__eq__`...): confirmados 4 para 6 (`av_real_03` e
`ip_real_14` novos, corpo da função idêntico ao original).

Medição final (código de 01/10, release 8.5, 116 hipóteses distintas): nível 1 com veredito em 16
(3 confirmadas), nível 2 em 22 (6 confirmadas), 78 só com a LLM. Controle do nível 1 nas versões
corrigidas: 0 confirmações. Ressalvas: o agente nunca rodou nas versões corrigidas (falta o controle
do nível 2), e nunca rodou sem o plugin (não se sabe quanto do ganho é do plugin e quanto é do ciclo
do Claude Code).

Depois da segunda revisão de código: a reexecução roda sem rede (`unshare --net`), o processo
principal reconfere que a linha reportada está no trecho da hipótese, e o filtro do sandbox fecha os
caminhos de fuga conhecidos (`from typing import sys`, `getattr` com nome montado, `operator.attrgetter`,
atributos `ag_`/`co_`). O código reexecutado ainda roda no mesmo processo que grava o resultado;
isolamento total exigiria outra arquitetura.

O prompt do agente agora proíbe módulos locais (`np.py` impedia a reexecução).

## Agente por API e simplificação conferida

- **Agente por API** (`--backend openai|google|ollama|claude_cli` no script, `--agent-backend` no
  pipeline): o mesmo ciclo do Claude Code, mas o pipeline roda o ESBMC e devolve o erro ao modelo, por
  até 8 rodadas, com as notas do ESBMC-Python no prompt. Testado em `ip_real_14` com `claude_cli`
  (o Claude só como texto, sem ferramentas nem plugin) e com `google` (gemini-2.5-flash): CONFIRMED
  nos dois, com o corpo da função intacto. A conta da OpenAI estava sem crédito em 01/10, e o Ollama
  local não tinha modelo baixado. Os relatórios de entrada (`artifacts/v2/engine-2026-10-01` e
  `engine-fixed-2026-10-01`) ficam fora do git, como os demais artefatos.
- **Simplificação conferida** (`--allow-simplify`): o agente pode simplificar o corpo onde o ESBMC
  recusa; só conta (`CONFIRMED_SIMPLIFIED`, nível à parte) se os valores do contraexemplo do ESBMC,
  sozinhos, quebrarem a função original no CPython. Nos 4 harnesses de 30/09 em que o agente mexeu na
  função (sem ter sido pedido), nenhum confirmou por essa regra.

## Achados sobre o ESBMC

- O master atual (01/10) não muda nada em 21 de 22 sondas mínimas montadas com as falhas de 30/09; a
  única diferença é uma falha interna nova com `dict[str, Optional[int]]`. Não vale trocar de versão.
- `re.match` com padrão de até 1 caractere sempre retorna verdadeiro no modelo
  (`src/python-frontend/models/re.py`, função `match`). Isso esconde bugs:
  `if re.match("a", s): return 0` seguido de `10 // len(s)` dá SUCCESSFUL mesmo com `s = ""`.
- Há dois binários na máquina: a rodada de 30/09 usou `/usr/local/bin/esbmc` (release 8.5, que
  imprime avisos do mypy, com Bitwuzla, Boolector, Z3 e CVC5); o `esbmc` do PATH é o build do PR
  #8014 e só tem Z3. Comparar rodadas só com o mesmo binário.
- Método de usuário chamado `get` é resolvido como `dict.get` (`super().get()` numa classe própria
  dá "get() missing required argument: 'key'").
- Falhas internas novas, alcançadas depois que o harness passou a aceitar mais suposições:
  `symbolic_type_excp` (`dz_real_03`) e `irep2: struct_union_member_names()` (`nm_real_25`).
  Candidatas a issue com reprodutor mínimo.
- `namedtuple` não existe no ESBMC; trocar por classe mudaria `==` e indexação sem erro visível, por
  isso o harness não reescreve.

## O que ainda trava

- 17 bugs sem o arquivo completo em `detection_full/`. O download funciona, mas foi rejeitado com
  `function_differs`: a função em `detection/` é um recorte curado (linhas removidas, assinatura
  simplificada; em `vm_real_04` é outro trecho da função). Encaixar a função curada no arquivo
  completo daria os imports e auxiliares que faltam; é decisão de método, ainda não tomada.
- Limites do ESBMC: `*args/**kwargs`, `async`, `type(x).__name__`, `x.__dict__`, fatiamento 2-D de
  numpy, classe que referencia a si mesma.
- `%` sobre variável de laço ou com `%d` em atributo sem tipo continua sem reescrita, porque a
  equivalência exata não pode ser provada.
