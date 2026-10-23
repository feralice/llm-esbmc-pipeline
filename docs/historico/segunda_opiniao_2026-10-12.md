Você está no repositório de pesquisa de uma mestranda (/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc).
Não edite nenhum arquivo. Só leia, rode comandos de leitura e, se quiser, rode o ESBMC em cópias dentro de
/tmp/codex-ideias/. Responda em português, sem travessão.

## O pedido

O pipeline LLM + ESBMC-Python confirma formalmente só 7 de 289 bugs reais. O gargalo agora é o ESBMC
recusar ou não terminar os programas. Quero ideias CONCRETAS e TESTÁVEIS para contornar as limitações do
ESBMC no harness, antes de mandar o programa a ele: stubs, modelos, reescritas do código ao redor e
reescritas da própria função que preservem o comportamento. Ordene pelo número de hipóteses que cada
ideia destrava, cite os casos (arquivo, hipótese) e, se possível, prove com uma sonda no ESBMC.

## Como o pipeline funciona

1. Detecção: o LLM aponta bug (função, expressão, linha). Prompt final A5.
2. Harness (src/research_pipeline/verify/): grounding.py recorta a função e o contexto; slicing.py poda
   classes e gera stubs de imports; render.py monta o programa (receptor com estado nondet, driver com
   nondet_* e __ESBMC_assume); compat.py faz reescritas de compatibilidade equivalentes.
3. ESBMC master (~/esbmc-master/build/src/esbmc/esbmc, Z3) com
   `--unwind 5 --multi-property --no-pointer-check --no-align-check`.
4. Validação: o CPython reexecuta o programa ORIGINAL com os valores do contraexemplo; só é CONFIRMED se
   a mesma exceção acontece na linha do bug. A versão corrigida do bug serve de controle.

Regras: nada ajustado a um caso específico do dataset (regras gerais); a versão corrigida e o patch não
podem ser usados para decidir; evidência só do CPython não conta como confirmação. Reescrever a função
com bug é aceitável se preservar o comportamento, porque a confirmação continua exigindo que o código
original quebre no CPython com a mesma entrada na mesma linha.

## Dados

- Reverificação mais recente: artifacts/v2/esbmc-master-flags2-2026-10-12/report_*of4.json (232
  hipóteses; campos verdict, reason, program_path; os programas gerados estão em programs/).
- Gabarito: dataset/bugs_reais/ground_truths.json; código: dataset/bugs_reais/arquivo_com_bug/.
- Limitações já isoladas: docs/projeto/possiveis_problemas/ (24 reprodutores, README com estado no master).
- Histórico de experimentos: docs/experimentos/README.md (fases 1 a 11).

Barreiras na reverificação com o master (188 hipóteses bloqueadas, contagem aproximada):

| Mensagem | Hipóteses |
|---|---|
| Function "x" not found (parâmetro que é função, ou variável local que guarda função: opfunc, cls, aggfunc) | 20 |
| Object "x" not found (nome de módulo ou constante fora do recorte) | 12 |
| Could not resolve type of receiver in member call (atributo de self sem tipo) | 12 |
| Variable 'args' is not defined in function (classe fora do caminho com *args/**kw) | 11 |
| entry point is nested inside a function | 10 |
| list indices must be integers (base importada trocada por classe vazia, código faz self['x']) | 9 |
| external call uses *args/**kwargs ou cannot be stubbed | 15 |
| input/stub unpacked into N names needs tuple | 9 |
| str % formatting com argumento não constante | 5 |
| Unsupported expression Starred | 4 |
| Cannot resolve attribute: shape (numpy) | 4 |
| irep2_cast_error, symbolic_type_excp (erros internos) | 9 |

Além disso, ESBMC_MISSED/timeout por laços de string nos modelos em C (str.lower, strlen, memcpy):
ip_real_22 e oob_real_12 quebram no CPython na linha do bug, mas o ESBMC não chega lá nem com
--unwind 25 em 600 s.

## Já tentado (não repetir sem ideia nova)

- 5 técnicas de prompt na detecção: nenhuma passou do ruído.
- Agente que escreve o harness à mão, busca de entrada no CPython e ESBMC com entrada fixada: 0
  confirmações formais novas.
- Função guardada em lista (opfunc): o ESBMC dá erro interno; trocar a tabela por objetos com __call__ é
  aceito, mas não chega ao ZeroDivisionError (para no laço de comparação de string).
- Receptor construído com argumentos: agora vira subclasse _Receiver (feito em 12/10).

## Formato da resposta

Para cada ideia: o que fazer (em qual arquivo do harness), quais hipóteses destrava (contagem e
exemplos), risco para a validade da prova, como testar em menos de 1 hora. Depois, uma lista curta do que
NÃO vale a pena. No fim, sua estimativa honesta de quantos bugs a mais dá para confirmar.
