# Log de literatura (loop autônomo)

Um item por artigo lido em função de um ciclo do loop `/loop 1h`. Formato fixo por item,
preenchido só depois de conferir a fonte primária (nunca por resumo de terceiros). Metadados
formais (DOI, autor verbatim) ainda precisam passar pelo mesmo processo de verificação usado no
`docs/LEITURAS_RECOMENDADAS.md` antes de qualquer citação fora deste log.

## Modelo de entrada

```
### <título> (<ano>)

- Referência: <autores completos, veículo>
- Link: <url>
- Problema tratado: <1-2 frases>
- Técnica proposta: <1-2 frases>
- Benchmark: <o que os autores mediram, em cima de quê>
- Métricas: <as métricas que os autores reportaram>
- Resultado principal: <número(s) central(is) do paper>
- Hipótese aplicável aqui: <como isso viraria uma mudança concreta no pipeline>
- Diferença benchmark deles vs dataset daqui: <honesto sobre o que não bate>
- Limitação da comparação: <o que a comparação não prova>
```

---

### Type-Constrained Code Generation with Language Models (2025)

- Referência: Niels Mündler, Jingxuan He, Hao Wang, Koushik Sen, Dawn Song, Martin T. Vechev.
  Proceedings of the ACM on Programming Languages, vol. 9, issue PLDI. PLDI 2025.
- Link: <https://doi.org/10.1145/3729274>
- Problema tratado: LLM gera código que não compila porque o próximo token não modela regras
  formais de tipo da linguagem; em TypeScript, ~94% dos erros de compilação são violação de tipo,
  não de sintaxe.
- Técnica proposta: decodificação restrita por tipo (`type-constrained decoding`), usando
  autômato de prefixo e inferência de tipo pra só permitir token que mantém o código bem tipado.
- Benchmark: HumanEval e MBPP, tarefas de síntese, tradução e reparo de código, vários modelos
  incluindo modelos abertos de 30B+.
- Métricas: taxa de erro de compilação, correção funcional.
- Resultado principal: reduz erro de compilação em mais da metade, aumenta correção funcional.
- Hipótese aplicável aqui: **inversa, não direta**. O problema deles é código mal tipado; o
  problema achado no EXP-02 (`docs/experiment_log.md`) é código **bem** tipado que ainda assim
  não prova nada, porque o tipo declarado do parâmetro (`nondet_bool()`) já elimina por
  construção a condição que o assert testa (`isinstance(param, bool)` é sempre verdade se `param`
  só pode ser `bool`). O paralelo que vale: os dois mostram que o sistema de tipos da linguagem
  interage com a geração da LLM de um jeito que o prompt sozinho não controla bem, e que checagem
  automática (deles: decodificação restrita; aqui: `compat.py`) precisa ficar entre a LLM e o
  resultado final.
- Diferença benchmark deles vs dataset daqui: eles medem compilação/correção funcional geral de
  código de propósito geral; aqui é síntese de harness escalar restrito pra um model checker,
  domínio bem mais estreito, sem comparação direta de número.
- Limitação da comparação: não dá pra usar o número deles (redução de erro de compilação) como
  baseline de nada aqui — é motivação conceitual, não benchmark comparável. A técnica deles
  (decodificação restrita) exigiria acesso aos logits do modelo, que os backends usados aqui
  (API OpenAI, `codex exec`) não expõem — não é diretamente aplicável sem uma mudança de
  arquitetura maior (modelo local com acesso a logits).
