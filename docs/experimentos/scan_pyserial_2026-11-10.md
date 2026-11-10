# Varredura do pyserial, 10/11/2026

Comando informado para a rodada:

```sh
python src/main.py --mode scan --input ~/alvos/pyserial --backend claude_cli --scan-limit 20 --output-dir artifacts/scan_pyserial_2026-11-10 --yes
```

A saída está em `artifacts/scan_pyserial_2026-11-10/`. Foram analisadas 20 funções; o resumo registra 32 hipóteses enviadas ao ESBMC e cinco retidas pela LLM. O ESBMC usado na rodada informou versão 8.6.0. O grafo resolveu 481 de 2.743 chamadas identificadas, portanto não descreve todas as relações entre funções.

Os vereditos registrados foram 2 `CONFIRMED`, 3 `UNVALIDATED`, 3 `OTHER_FAILURE`, 1 `NOT_CONFIRMED`, 3 `ESBMC_TIMEOUT`, 2 `ESBMC_ERROR`, 17 `LLM_ONLY` e 1 `BOUND_INCONCLUSIVE`. Esses totais são os do resumo da ferramenta, não uma contagem de defeitos reais. `LLM_ONLY` é uma hipótese sem decisão do verificador; timeout, erro e limite inconclusivo também não demonstram presença nem ausência de defeito. `NOT_CONFIRMED` não prova que a função seja segura em todas as entradas.

## Revisão dos dois confirmados

Os programas `48f8b0af4b96_a0.py` e `a7a990b400a1_a0.py` criam `_rfc2217_options` vazio e só adicionam até duas chaves arbitrárias. Assim podem lançar `KeyError` para `control` ou `purge`. No código real, `open()` cria as duas chaves, com objetos `TelnetSubnegotiation`, antes de usá-las. Isso sustenta a suspeita de falso positivo por estado artificial para o fluxo normal de abertura, não uma prova geral sobre todos os estados possíveis do objeto.

Em `verify/render.py`, `_Declarer._shape` começa dicionários com `{}` e inclui elementos sob escolhas não determinísticas; `_shell_init` substitui a inicialização do objeto. `verify/grounding.py`, em `constructor_guards`, extrai algumas condições do construtor, mas não os efeitos de `open()`; `verify/rules.py` enumera transformações de compatibilidade, não invariantes de estado. O replay em CPython executa uma cópia do programa gerado e suas escolhas, não reconstrói necessariamente o ciclo de vida real: ele pode reproduzir o `KeyError` artificial sem detectar que o estado é inalcançável.

Proposta para avaliação: registrar chaves obrigatórias e seus valores ou tipos com evidência de uma inicialização que domina a chamada, incluindo condições de sucesso de `open()`, e gerar o objeto com essas chaves. Uma sugestão da LLM deve ser tratada como hipótese, com origem e validação no código; não se deve presumir que uma chave esteja presente só porque o método a acessa. Quando não for possível estabelecer o estado alcançável, informar a limitação e não classificar a reprodução na abstração como confirmação no projeto. Não foi implementada esta proposta.

## Recusas registradas

| Motivo | Funções afetadas nesta rodada | Situação e contorno |
|---|---|---|
| Tipo desconhecido em subscript | `Serial.from_url` em `protocol_spy.py`, `protocol_loop.py`, `protocol_socket.py` e `rfc2217.py` | Ainda não foi demonstrado um contorno que preserve os tipos, valores e exceções de `parse_qs`; issue específica não confirmada. |
| `bytearray` não suportado | `SerialBase.read_until` em `serialutil.py` | [#10207](https://github.com/esbmc/esbmc/issues/10207) está aberta. A regra `compat_bytearray` já cobre somente alguns usos e evita converter listas para `bytes` em casos em que o ESBMC 8.6 modela o comprimento incorretamente. Contorno seguro para este caso ainda não demonstrado. |
| Atributo aninhado `argtypes` | `iterate_comports` em `list_ports_windows.py` | A issue de acompanhamento [#8326](https://github.com/esbmc/esbmc/issues/8326) menciona limitações de atributos aninhados, mas não estabelece que cubra este uso de ctypes. Contorno equivalente ainda não demonstrado. |

As issues [#10234](https://github.com/esbmc/esbmc/issues/10234) e [#10235](https://github.com/esbmc/esbmc/issues/10235) tratam, respectivamente, de desempacotamento aninhado e de `array.array`; não são evidência de cobertura dessas recusas. A [#10241](https://github.com/esbmc/esbmc/issues/10241) trata de uma chave de tipo desconhecido que causa `KeyError` falso, e não demonstra cobertura da recusa de um valor indexado de tipo desconhecido.

Outras melhorias possíveis para avaliação: distinguir no resultado a reprodução apenas no harness da reprodução com o estado real reconstruído; apresentar as premissas e a origem de cada atributo ao lado do veredito; e agrupar recusas pelo erro efetivo com links para issues verificadas. São propostas, não alterações já implementadas.

## Crashes e pendências

Na instalação usada pela rodada, executei os dois programas com `--segfault-handler`; ambos produziram sinal 11. Atualizei `~/esbmc-master` para `bd14e113c99cf6d41d481294d34e1844f2167445` e recompilei com `ninja -C ~/esbmc-master/build-bw esbmc`. O binário resultante informa versão 8.6.0. Os dois programas originais também terminaram com sinal 11 nessa revisão, o segundo com `--unwind 10`. Em ambos, a saída aponta a etapa de codificação das condições para o solucionador Bitwuzla. A redução, a identificação precisa por símbolos, a análise de duplicatas e os contornos ainda não estão concluídos; a hipótese do fatiamento não foi confirmada.

Não houve nova rodada da LLM nem gasto de API nesta investigação. Codex foi usado para inspecionar os artefatos, executar comandos e redigir este registro; Fernanda deve conferir as evidências e avaliar as interpretações.

## Complemento da investigação

Atualizei novamente `~/esbmc-master` com `git pull --ff-only` e recompilei com `ninja -C ~/esbmc-master/build-bw esbmc`. No commit `7c91b097bf9cf31c8b2cd35357e69f367ba9e1cc`, versão 8.6.0, os dois programas originais continuam terminando com sinal 11, o segundo com `--unwind 10`. Com `--segfault-handler`, ambos caem durante a codificação para Bitwuzla. No primeiro, a tradução dos endereços indica acesso ao cache de expressões SMT; no segundo, indica `bitwuzla_convt::mk_bvsge` em `src/solvers/bitwuzla/bitwuzla_conv.cpp:468`. Isso localiza a falha observada, mas não estabelece sua causa.

Um teste reduzido com `nondet_bytes(2)` guardado em atributo `raw` e fatiado por um atributo inteiro também caiu, mas em uma etapa anterior à codificação SMT observada no original. Assim, ainda não está demonstrado que seja o mesmo defeito. O teste de três linhas com bytes e índice em variáveis locais terminou com `VERIFICATION SUCCESSFUL`; portanto, não é correto atribuir o crash a qualquer fatiamento de bytes. Ainda falta isolar quais componentes são necessários e reduzir o segundo caso. Não há contorno comprovado nem rascunho de issue pronto. Entre os relatos localizados estão a issue fechada [#9445](https://github.com/esbmc/esbmc/issues/9445), sobre fatiamento de strings, e a [#9839](https://github.com/esbmc/esbmc/issues/9839), sobre subscript de tupla em atributo; a duplicação para estes exemplos não foi estabelecida. O PR aberto [#7470](https://github.com/esbmc/esbmc/pull/7470) trata de operandos nulos no conversor SMT, mas não foi demonstrado que corrija estes casos.

O harness da leitura também substitui `ctypes.create_string_buffer` por `nondet_bytes(2)`, enquanto o método acessa `buf.raw`. Essa substituição não conserva a interface real do objeto: `bytes` não tem atributo `raw` em CPython. É uma limitação do harness que precisa ser tratada separadamente do crash do verificador. No caso RFC 2217, o harness substitui constantes do módulo `serial` por valores não determinísticos e permite `_baudrate` como `None`; não foi demonstrado que alguma dessas escolhas cause o crash ou represente um estado válido da aplicação.

Posteriormente foi acrescentada uma verificação da especificação: quando o stub `ctypes.create_string_buffer` retorna `bytes` e o resultado atribuído é usado com `.raw`, o pipeline informa a incompatibilidade antes de gerar esse harness. A verificação também foi exercitada sobre o código real de `Serial.read`. Isso evita essa simulação incorreta, mas não implementa um buffer mutável nem verifica o efeito de `ReadFile`; tampouco corrige o ESBMC ou resolve os demais casos. Os resultados da rodada anterior não foram alterados retroativamente.

Na validação da alteração, 69 testes focados passaram. A suíte completa teve 1.643 aprovados, 1 ignorado e 24 falhas. Uma falha examinada depende de escrita em `~/.cache`, bloqueada neste ambiente; outra espera uma única regra de reparo automático, mas encontra várias no caderno já existente. As demais falhas não foram todas investigadas, portanto não se pode afirmar que a suíte completa passou ou que todas sejam anteriores à mudança.
