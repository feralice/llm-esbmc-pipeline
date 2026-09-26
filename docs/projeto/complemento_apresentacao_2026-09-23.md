# Complemento da apresentação: 23/09/2026

Texto pronto por slide, para colar no Canva. Continuação de
[`complemento_apresentacao_2026-09-09.md`](complemento_apresentacao_2026-09-09.md).

---

**Slide 1: Título**

Pipeline híbrido LLM + ESBMC-Python: progresso desde 09/09/2026

Subtítulo: catorze dias, vinte e quatro commits, uma rodada end-to-end completa.

---

**Slide 2: Mensagem central**

Principais mudanças desde 09/09:

- pipeline mais robusto para execuções longas, com novos backends e tratamento
  de falhas de API e checkpoint;
- dataset auditado e avaliação corrigida: 120 casos revisados, 3 duplicatas
  removidas e 94 casos realmente elegíveis;
- geração de harness mais confiável, com validação, reparo automático e uma
  rodada end-to-end completa;
- resultados agora separam claramente erro de detecção, erro no harness e
  confirmação formal pelo ESBMC;
- revisão de seis trabalhos recentes para orientar os próximos experimentos.

---

**Slide 3: O que mudou (robustez)**

- Checkpoint sobrevive a falha de escrita em disco (`OSError`) sem derrubar
  o loop de detecção inteiro.
- Pipeline distingue cota diária esgotada de throttling por minuto, nos
  quatro backends que chamam API.
- Chave `ANTHROPIC_API_KEY` isolada do ambiente do subprocesso antes de
  chamar `claude -p`, sem custo por token.
- Bug de resolução de modelo corrigido: o modo V2 resolvia o modelo padrão
  contra um backend fixo em vez do backend escolhido na linha de comando,
  quebrando a execução com o backend Gemini.
- Integração da geração de contra-testes Python com `pytest` disponível como
  opção do fluxo V2; o caminho e o status do artefato ficam no relatório.

---

**Slide 4: Novos backends**

Adicionados `claude_cli` e `gemini_cli`, que chamam a assinatura já paga via
CLI local em vez da API cobrada por token.

Com isso, três backends completos rodam detecção e síntese de harness sem
nenhum custo por token: `codex`, `claude_cli` e `gemini_cli`.

---

**Slide 5: Dataset e correção metodológica**

Auditoria de proveniência do dataset de mundo real:

- 120 arquivos provenientes de 42 repositórios;
- 3 entradas duplicadas removidas (mesmo commit e mesma função);
- 94 casos elegíveis para a avaliação da LLM;
- 26 casos excluídos porque sua categoria não pode ser determinada apenas pelo
  código bugado: dependem do contexto do patch ou não se encaixam na
  taxonomia oficial.

Também foi corrigido um filtro que não estava sendo aplicado: a LLM recebia os
120 casos, e acertos nos 26 casos não avaliáveis eram registrados como falsos
positivos por não terem correspondência no gabarito. Um teste de regressão
confirmou o comportamento correto antes e depois da correção.

---

**Slide 6: Estudos novos**

Seis trabalhos relacionados ao ciclo **LLM → feedback → correção**:

- **Self-Debug (ICLR 2024):** LLM corrige o próprio código.
- **Reflexion (NeurIPS 2023):** LLM reutiliza reflexões de tentativas anteriores.
- **CRITIC (ICLR 2024):** ferramentas externas orientam a correção da LLM.
- **HarnessLLM (ICSE 2026):** geração e refinamento automático de harnesses.
- **Invariantes LLM (ASE 2024):** sugestões da LLM são aceitas após prova formal.
- **Effectiveness Decay (Scientific Reports 2025):** retries podem perder eficácia.

**Contribuição para o trabalho:** fundamentam o uso do ESBMC como feedback
externo e a necessidade de controlar as tentativas de síntese. O veripp aplica
ideia semelhante em C/C++, mas não cobre Python/ESBMC-Python.

---

**Slide 7: Como a avaliação funciona**

- A LLM analisa uma função e aponta uma categoria de bug.
- O programa confere se o trecho indicado existe no código.
- A LLM gera um harness para testar a hipótese.
- O ESBMC verifica o harness formalmente.

**Resumo:** a LLM propõe; o programa confere; o ESBMC decide.

---

**Slide 8: Resultado da nova rodada (modelo barato)**

Base: 94 arquivos e 102 bugs esperados.

- **Detecção:** 45 bugs encontrados na categoria correta; 57 não encontrados.
- **Geração do harness:** 33 de 40 hipóteses produziram harness compatível.
- **Resultado final:** 13 hipóteses foram confirmadas formalmente.
- **O ESBMC confirmou 44 bugs ao todo:** 13 na categoria esperada e 31 em
  categorias diferentes.

**Mensagem principal:** o maior problema é a classificação da LLM. Dos 40
casos encaminhados à geração do harness, 33 eram compatíveis. A avaliação agora
separa confirmação do código real de confirmação apenas da abstração escalar:
esta última continua sendo útil como diagnóstico, mas não é contada como
confirmação end-to-end do bug original. O ground truth só é usado na avaliação
final; não é enviado à LLM nem ao ESBMC. O ESBMC teve poucas falhas próprias;
seus resultados expuseram problemas na hipótese ou no harness.

---

**Slide 9: Onde a detecção erra**

O modelo geralmente encontra o arquivo que contém um bug, mas erra a
categoria.

O gabarito não é enviado à LLM nem ao ESBMC. Ele só é usado depois, para
comparar a categoria prevista com a categoria esperada.

**Categoria prevista pela LLM / categoria esperada no ground truth:**

- `invalid_precondition`: 47 / 30;
- `none_misuse`: 44 / 27;
- `variable_misuse`: 1 / 10;
- `integer_overflow`: 0 / 2.

**Conclusão:** o gargalo é classificar o tipo do bug, não encontrar código
suspeito.

**Exemplo real, caso `ip_real_14` (keras, `TimeseriesGenerator.__len__`):**

```python
def __len__(self):
    return int(np.ceil(
        (self.end_index - self.start_index) /
        (self.batch_size * self.stride)))
```

O gpt-4o-mini apontou exatamente essa linha, mas como `division_by_zero`,
porque `batch_size * stride` pode ser zero. O gabarito registra
`invalid_precondition`: a correção oficial acrescenta a checagem
`start_index <= end_index` e soma 1 ao intervalo, que deveria incluir
`end_index`. O modelo encontrou o lugar certo, mas descreveu outro defeito.

**Segundo exemplo, caso `vm_real_09` (tqdm, `Progress.__len__`):**

```python
def __len__(self):
    return self.total if self.iterable is None else (
        len(self.iterable) if hasattr(self.iterable, "__len__")
        else self.total
    )
```

O bug real é ler `self.total` no último ramo quando esse atributo não foi
definido (`variable_misuse`). O gpt-4o-mini apontou `len(self.iterable)` como
`none_misuse`, mas essa chamada é protegida pelas checagens anteriores. Aqui o
modelo errou a categoria e o trecho, dentro da função correta.

---

**Slide 10: Onde o harness erra**

O harness é o pequeno programa de teste criado pela LLM. Mesmo quando a
categoria está correta, esse programa pode testar a coisa errada.

Principais erros:

- o resultado da função é calculado, mas não é usado em um `assert`;
- `isinstance()` testa um tipo que já é garantido, sem explorar o caso inválido;
- o `assert` verifica uma propriedade diferente da hipótese.

**Exemplo real, caso `ip_real_17`, função `response_status_message`:**

Código analisado:

```python
def response_status_message(status):
    return '%s %s' % (
        status,
        to_native_str(http.RESPONSES.get(int(status)))
    )
```

Hipótese correta: `http.RESPONSES.get(int(status))` pode retornar `None` para
um status que não existe.

Harness gerado pela LLM:

```python
def model():
    status = nondet_int()
    response_value = nondet_str()
    result = response_value
    assert result == result
```

**Por que está errado:**
- `status` é criado, mas nunca é passado para a função original;
- `response_value` é um valor inventado, não o resultado de
  `response_status_message(status)`;
- `assert result == result` sempre é verdadeiro.

Assim, o harness não executa `http.RESPONSES.get(int(status))`. O ESBMC
verifica esse harness, mas não chega ao trecho que contém o possível bug.

---

**Slide 11: Novas tentativas e dúvidas**

**O que foi estudado nos últimos 15 dias: veripp**

- O Python gera deterministicamente o harness; o ESBMC verifica o resultado.
- O LLM é opcional: interpreta o contraexemplo e pode sugerir ajustes ou
  pré-condições para uma nova rodada.
- O veripp valida compilação, alcançabilidade da função e hipóteses usadas. Uma
  prova que não exercita a função é marcada como `VACUOUS`.
- Aproveitamos essa separação, mas não o gerador diretamente: ele foi feito
  para C/C++ (`main`, ponteiros e structs), enquanto Python exige tratar
  imports, tipos dinâmicos e `assert`s.

**Novas tentativas**

- **Pytest depois do ESBMC:** executar `esbmc --generate-pytest-testcase
  harness.py` para gerar um teste reproduzível com os valores do contraexemplo.
- O Pytest reproduz o resultado; não gera o harness inicial nem substitui as
  flags de verificação. A opção é opt-in e falhas na geração não alteram o
  veredito original do ESBMC. O pipeline valida a sintaxe do arquivo e marca
  `invalid_generated_test` quando o ESBMC emite Python inválido.

**Como o harness é feito hoje**

- Primeiro, o pipeline tenta verificar a função real diretamente.
- Depois, tenta um driver que mantém o trecho real e adiciona apenas as
  entradas e o `assert`.
- Se essas opções não funcionam, cai no harness escalar: a LLM reconstrói só a
  expressão suspeita com valores `nondet_*`, sem chamar a função original.
- É nesse último fallback que pode acontecer o problema do `ip_real_17`: o
  harness executa, mas não testa o código real.

**Regra metodológica da avaliação:** confirmações dos tiers `native`,
`real_body` e `driver` podem sustentar a confirmação final do código original.
Uma confirmação com `harness_tier="scalar"` é registrada separadamente como
confirmação da abstração e não aumenta a métrica end-to-end.

**Dúvidas para discutir**

1. Encontrei um bug no ESBMC-Python: ele não detecta `None` vindo de função
   com entrada `nondet` nem de `dict.get`. Abro a issue?
2. O harness escalar não testa o código real. Podemos descartá-lo como
   evidência?
3. Executar a função real com a entrada sugerida pela LLM serve como
   confirmação antes do ESBMC?
4. Quando duas categorias fazem sentido, aceitar uma alternativa na avaliação?
5. O `--generate-pytest-testcase` deve ser usado como reprodução do
   contraexemplo do ESBMC; ele não é, sozinho, evidência de que o harness
   representa o bug real.

---

**Slide 12: Próximos passos**

**Prioridade alta:**
- Separar a decisão da LLM: primeiro identificar se há bug e onde; depois
  classificar uma das 8 categorias.
- Executar a estratégia `two_stage` em rodadas controladas, comparando-a com a
  estratégia `single` e guardando os resultados brutos por rodada.
- Criar few-shots específicos para `variable_misuse` e `integer_overflow`.
- Preservar partes corretas do harness durante novas tentativas.

**Flags já incorporadas na verificação formal:**
- `type_mismatch`: `--is-instance-check` orienta a verificação dos testes de
  tipo feitos com `isinstance()`;
- `integer_overflow`: `--overflow-check` e `--unsigned-overflow-check` fazem o
  ESBMC procurar estouro com e sem sinal.

As flags não corrigem o harness; apenas orientam o que o ESBMC deve verificar.

---

**Slide 13: Extensão para a disciplina**

Projeto próprio de PGENE601/PPGINF554: reaplicar o mesmo método, sem mudar
arquitetura nenhuma, a bugs reais de software Python de sistemas
ciber-físicos e embarcados (MicroPython, CircuitPython, robótica).

Escopo pequeno e contido (5 a 10 bugs), cronograma fixo da disciplina, sem
competir por tempo com a dissertação. Uma possibilidade é incluir condição de
corrida como categoria nova: o ESBMC-Python já suporta um subconjunto de
`threading` com `--data-races-check`, mas ainda seria necessário integrar e
avaliar essa categoria no pipeline.
