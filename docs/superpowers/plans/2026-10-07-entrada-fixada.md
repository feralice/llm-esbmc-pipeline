# Entrada fixada: plano de implementação

> Execução: superpowers:executing-plans, nesta sessão. TDD em cada etapa.

**Objetivo:** confirmar formalmente uma entrada encontrada pelo CPython quando o ESBMC esgota tempo ou memória.
**Especificação:** `docs/handoff/CODEX.md`, tarefa 2; `docs/ESTADO.md`.
**Arquitetura:** o replay guarda valores em ordem de execução. O programa fixado troca apenas chamadas de intrínsecos do harness por funções tipadas que consomem essa sequência. O braço `pinned` verifica esse programa e reproduz exatamente a mesma entrada no código preservado.
**Tecnologias:** Python, pytest, ESBMC-Python 8.5.0.

## Restrições

- Nenhuma chamada a API paga; sem commit sem autorização.
- Preservar a função original e as assumptions. Nunca desabilitar unwinding assertions.
- Regras gerais, sem nomes ou valores de casos do dataset na implementação.
- Rejeitar entrada ausente, inconsistente ou não representável; não completar uma entrada fixada com busca.
- Medir nos 20 casos difíceis e nas versões corrigidas; registrar e arquivar a rodada.

## Pontos de revisão

- Chamadas em ramos e loops consomem valores em ordem dinâmica, não em ordem textual.
- `nondet_list` consome o argumento, o comprimento e os elementos, preservando seus limites.
- Uma entrada vazia difere de uma entrada ausente; booleanos não são inteiros neste protocolo.
- Compatibilidade e stubs não podem substituir a reexecução do código preservado.
- Retomada deve recuperar os valores do braço dinâmico; fracasso formal não apaga FUZZ_FOUND.

## Etapa 1: captura e reexecução exata

Arquivos: `verify/replay.py`, `verify/replay_worker.py`, `tests/test_verify_replay_pinned.py` (sob `src/research_pipeline` para produção).
Interface: `ReplayVerdict.inputs: list | None`; `concrete_replay(..., inputs: list | None = None)`.

- [ ] Escrever testes: valores exaustivos e aleatórios, entrada exata que passa, entrada que quebra, sequência incompatível e listas.
- [ ] Executar os testes e observar falhas por funcionalidade ausente.
- [ ] Guardar valores em ambos os choosers; adicionar execução única estrita com a sequência informada.
- [ ] Executar os testes de replay e dinâmica.

## Etapa 2: programa fixado e braço formal

Arquivos: `verify/pinned.py`, `tests/test_verify_pinned.py`.
Interfaces: `pin_program(program: Program, inputs: list) -> Program`; `pinned_check(result: dict, *, dynamic: dict, work_dir: Path, esbmc_command: list[str], bound: int, timeout_seconds: int) -> dict`.

- [x] Sondar o ESBMC real com função tipada que devolve valores constantes em sequência.
- [ ] Testar preservação do alvo, strings vazias, loops, listas, tipos e limites de entrada.
- [ ] Implementar substituição de chamadas e helpers com cursor compartilhado; assumptiom falsa se a sequência terminar ou o tipo divergir.
- [ ] Reproduzir a entrada no programa original; executar `esbmc_run.check` e combinar por `outcome.final_verdict`.
- [ ] Verificar caso inventado com bug e sua versão corrigida no ESBMC real.

## Etapa 3: integração e medição

Arquivos: `verify/routing.py`, `verify/orchestrator.py`, `scripts/v2_orchestrate.py`, testes correspondentes, documentos de estado e experimentos, `scripts/archive_runs.py`.

- [ ] Testar `ESBMC_TIMEOUT -> dynamic -> pinned`, desvio sem FUZZ_FOUND e retomada entre braços.
- [ ] Disponibilizar `--arms dynamic,pinned`, mantendo resultado dinâmico quando a tentativa formal falhar.
- [ ] Medir os 20 casos e o controle corrigido, sem agentes ou API.
- [ ] Executar a suíte completa, revisar o diff e corrigir problemas relevantes com TDD.
- [ ] Atualizar estado/handoff com a métrica observada e arquivar a rodada na fase 10.

## Sonda (07/10/2026)

Comando: `/usr/local/bin/esbmc /tmp/esbmc-pinned-probe/values.py --unwind 5 --multi-property`.
Resultado: helper `str` com cursor global aceito; string vazia em `x[0]` resulta em `VERIFICATION FAILED`, `IndexError`. A propriedade de exceção é global (linha 0): a linha concreta vem do replay, limitação a registrar nos resultados.
