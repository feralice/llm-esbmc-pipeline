# Complemento da apresentação: 30/09/2026

Texto pronto por slide, para colar no Canva. Continua a apresentação de
23/09/2026 (disponível no histórico do git).

> **Nota:** números medidos em 29/09/2026 com gpt-4o-mini e ESBMC 8.5.0 oficial. Slides 12 e 13:
> rodadas com o motor completo; Slide 14: experimentos de controle com a versão final do motor.

---

**Slide 1: Título**

Pipeline híbrido LLM + ESBMC-Python: redesenho da verificação

Subtítulo: da síntese livre de harness para hipóteses congeladas, harness
determinístico e validação por execução.

---

**Slide 2: Mensagem central**

Principais mudanças desde 23/09:

- diagnóstico de por que o pipeline confirmava tão poucos bugs no código real;
- nova arquitetura em que a LLM não escreve mais código de verificação;
- substitutos automáticos para bibliotecas que o ESBMC-Python não modela;
- achados empíricos sobre falsos positivos e falsos negativos do ESBMC-Python 8.5;
- vereditos mais ricos, que separam erro da LLM, limite do método e limite do
  verificador;
- a LLM localiza a função com bug em 97% dos casos, e a primeira confirmação formal no
  código original sem nenhuma alteração da função.

---

**Slide 3: Diagnóstico da versão anterior**

Rodada de referência de 27/09 (gpt-4o-mini, 135 hipóteses):

- 25 hipóteses foram "confirmadas" apenas na abstração escalar, que não executa
  o código original; no código real, a confirmação ficou em 2 casos entre as
  detecções corretas;
- 22 dos 34 resultados inconclusivos não tinham motivo registrado, o que
  impedia separar falha da LLM de limitação do ESBMC;
- a verificação passava por seis estratégias em cascata, com 763 chamadas de
  síntese para 135 hipóteses;
- a categoria do bug guiava a geração e a métrica, penalizando acertos de
  localização com categoria diferente.

**Conclusão:** o problema principal estava na arquitetura da síntese, e não
apenas no modelo.

---

**Slide 4: Exemplo do problema (caso `ip_real_15`, black)**

Código real:

```python
while self.previous_defs and self.previous_defs[-1] >= depth:
    self.previous_defs.pop()
```

Hipótese da LLM: `pop()` em lista vazia. A hipótese é falsa, porque o `while`
já impede esse caso.

Harness gerado pela LLM na versão anterior: trocou a lista por um número
inteiro, removeu o `while` e verificou `previous_defs >= 0`.

Resultado: o ESBMC encontrou um contraexemplo e o caso foi contado como
confirmado na abstração. Um falso positivo da LLM foi "confirmado", porque o
harness verificava outra propriedade.

---

**Slide 5: Nova arquitetura**

Código real → LLM indica o bug → validação por AST → montagem do harness →
ESBMC → validação por execução

- **Hipótese congelada:** localização, expressão suspeita e condição de disparo
  não mudam entre tentativas.
- **Código original preservado:** a função analisada entra sem nenhuma
  alteração no programa verificado.
- **Harness determinístico:** montado pelo programa, e não pela LLM.
- **Reparo limitado:** no máximo duas correções, guiadas pelo erro do ESBMC.
- **Sem repetição de resultado seguro:** repetir até obter uma violação seria
  forçar a confirmação.

**Resumo:** a LLM propõe; o programa monta e confere; o ESBMC e a execução
decidem juntos.

---

**Slide 6: O que a LLM produz agora**

Em vez de um programa, a LLM devolve só uma descrição das entradas:

```json
{
  "params": {"depth": "int"},
  "attributes": {"previous_defs": "list[int]"},
  "stubs": {"to_bytes": "str"},
  "assumptions": []
}
```

- Tipos aceitos: inteiros, reais, booleanos, texto, bytes, listas e
  dicionários aninhados, tuplas, valores opcionais e objetos com campos.
- Pré-condições só podem usar as entradas e `len()`.
- Quando o tipo real não é representável, o caso é registrado como limite do
  método, e não como erro da LLM.
- A categoria do bug virou metadado: não participa da geração nem da
  confirmação.

---

**Slide 7: Bibliotecas ausentes**

O ESBMC-Python tenta abrir cada biblioteca importada e falha em pacotes como
tornado, scrapy, luigi e pandas. Na primeira execução real, 53 de 86 casos
pararam nesse ponto.

Agora cada uso de biblioteca não modelada recebe um substituto gerado pelo
programa:

| Uso no código | Substituto | Tipo |
|---|---|---|
| chamada de função ou método | função que devolve valor não determinístico | informado pela LLM |
| constante da biblioteca | valor não determinístico | informado pela LLM |
| classe base, anotação, `isinstance` | classe vazia | não precisa |
| exceção levantada ou capturada | subclasse de `Exception` | não precisa |
| cadeia `email.utils.parsedate_tz(...)` | referência renomeada para `email_utils.parsedate_tz` | informado pela LLM |
| classe instanciada e usada como tipo | classe com construtor vazio | não precisa |

Uma confirmação que depende de substituto é registrada como condicional: vale
se a biblioteca puder devolver aquele valor.

---

**Slide 8: Achados sobre o ESBMC-Python 8.5**

Testes controlados com a versão oficial 8.5.0:

| Programa | Execução real | ESBMC-Python 8.5 |
|---|---|---|
| `while defs and defs[-1] >= d: defs.pop()` | seguro | aponta `IndexError` (falso positivo) |
| `v: Optional[int] = None; v + 1` | `TypeError` | não detecta (falso negativo) |
| exceção não tratada | linha exata | reportada na linha 0 |

**Consequência:** o veredito do verificador sozinho não basta em nenhum dos dois
sentidos. A confirmação passou a exigir que o ESBMC aponte a violação **e** que
a execução concreta do mesmo programa reproduza a mesma exceção na linha da
hipótese (validação por execução, Beyer et al., TAP 2018).

---

**Slide 9: Novos vereditos**

| Veredito | Significado |
|---|---|
| Confirmado | ESBMC e execução concordam na exceção e na linha da hipótese |
| Falso negativo do ESBMC | a execução reproduz o bug, o ESBMC não detecta |
| Não validado | o ESBMC aponta violação que a execução não reproduz |
| Outra falha | a execução quebra em outra linha |
| Não confirmado | nenhum dos dois encontra o bug |
| Não suportado / dependência ausente | limite do método ou do dataset |
| Especificação falhou | a LLM não produziu uma descrição válida |

Só o primeiro conta como confirmação do bug real.

---

**Slide 10: Respostas às dúvidas de 23/09**

1. **Bug do ESBMC com `None`:** confirmado de forma independente. `Optional[int]`
   somado a inteiro não é detectado na versão 8.5; o caso agora é medido como
   falso negativo do verificador.
2. **Harness escalar como evidência:** descartado do caminho principal. Ele fica
   disponível apenas como linha de base para comparação.
3. **Executar a função real:** adotado como validação obrigatória depois do
   ESBMC, com os mesmos valores de entrada do programa verificado.
4. **Duas categorias possíveis:** a detecção passa a ser medida por localização
   (função e expressão); a categoria vira análise secundária.
5. **Pytest gerado pelo ESBMC:** substituído pela reexecução própria, que também
   valida a linha e o tipo da exceção.

---

**Slide 11: Cobertura do harness sem LLM**

Funil sobre 116 bugs reais de 42 projetos, apenas com as etapas determinísticas:

| Versão do harness | Aptos à verificação |
|---|---|
| primeira versão (tipos simples) | 64 |
| com stubs de biblioteca | 70 |
| com objetos, dicionários, listas aninhadas e tuplas | 72 |
| com `classmethod`, construtores e cadeias de biblioteca | **82** |

Os 34 restantes:

- 15 com dependência ausente, em sua maioria casos sem o arquivo-fonte completo no dataset;
- 15 com construções fora do alcance do verificador, como `async`, recorte do módulo que
  alteraria dados globais e decoradores de bibliotecas em outros métodos;
- 4 com localização inválida (funções aninhadas e trechos de nível de módulo).

---

**Slide 12: RQ1, a LLM encontra o bug?**

Rodada ponta a ponta (gpt-4o-mini, 104 arquivos avaliáveis, 138 hipóteses):

| Critério de acerto | Acertos | Precisão | Revocação |
|---|---|---|---|
| arquivo com bug | 102 de 104 | 100% | 98% |
| **função com bug** | **101 de 104** | **86%** | **97%** |
| categoria certa no arquivo | 51 de 104 | 30% | 49% |
| categoria certa, dado que a função está certa | 49 de 104 | | 47% |
| expressão idêntica à do gabarito | 21 de 104 | 12% | 20% |

**Conclusão:** a LLM localiza a função defeituosa quase sempre (97%), mas acerta a categoria em
cerca de metade dos casos, e o trecho exato em um quinto. Medir a detecção só pela categoria,
como até 23/09, subestimava a localização; por isso a categoria deixou de guiar a verificação.

---

**Slide 13: RQ2 e RQ3, o ESBMC confirma?**

| | RQ2 (localização do gabarito dada) | RQ3 (ponta a ponta) |
|---|---|---|
| hipóteses | 125 | 138 |
| chegaram à especificação pela LLM | 91 | 79 |
| **confirmadas no código original** | **3** | **1** (condicional) |
| falso negativo do ESBMC (execução reproduz, ESBMC não) | 0 | 1 |
| ESBMC aponta, execução não reproduz | 2 | 0 |
| não confirmadas (nenhum dos dois encontra) | 6 | 4 |
| paradas por limite do ESBMC ou do harness | 63 | 60 |
| dependência ausente | 26 | 21 |
| especificação inválida | 14 | 21 |
| tempo esgotado ou erro do ESBMC | 9 | 5 |
| localização inválida | 2 | 25 |

Verificação com veredito em até 1, 2 e 3 chamadas da LLM: 3%, 9% e 12% (RQ2); 5%, 6% e 8% (RQ3).

**Confirmações no código original:**
- `cli_bool_option` (youtube-dl, BugsInPy 17): o ESBMC acusa a falha do `assert isinstance(param, bool)`
  do próprio código, e a execução reproduz `AssertionError` na mesma linha.
- `match` (thefuck, BugsInPy 21): `command.script.split()[1]` com comando de uma palavra só; ESBMC
  e execução concordam no `IndexError`.
- `WebSocketHandler.set_nodelay` (tornado): `AssertionError` com o estado do objeto e a classe base
  substituídos; é a confirmação da ponta a ponta, condicional a esse estado.

**Leitura honesta:** o gargalo está no alcance do ESBMC-Python sobre código real, e não na LLM.

---|---|---|
| hipóteses | 125 | 138 |
| chegaram à especificação pela LLM | 76 | 64 |
| **confirmadas no código original** | **1** | 0 |
| falso negativo do ESBMC (execução reproduz, ESBMC não) | 0 | 1 |
| ESBMC aponta, execução não reproduz | 2 | 0 |
| não confirmadas (nenhum dos dois encontra) | 7 | 4 |
| paradas por limite do ESBMC ou do harness | 65 | 61 |
| dependência ausente | 26 | 24 |
| especificação inválida | 14 | 20 |
| tempo esgotado ou erro do ESBMC | 8 | 3 |
| localização inválida | 2 | 25 |

Verificação com veredito em até 1, 2 e 3 chamadas da LLM: 5%, 11% e 13% (RQ2); 5%, 6% e 8% (RQ3).

**Primeira confirmação:** `cli_bool_option` (youtube-dl, BugsInPy 17). O ESBMC acusa a falha do
`assert isinstance(param, bool)` do próprio código, e a execução reproduz `AssertionError` na
mesma linha, sem nenhuma alteração na função.

**Leitura honesta:** o gargalo está no alcance do ESBMC-Python sobre código real, e não na LLM.

Custo da rodada ponta a ponta: cerca de 680 mil tokens (258 mil na detecção e 423 mil na
especificação).

---

**Slide 14: Experimentos de controle**

Mesmas 125 hipóteses do gabarito (RQ2), gpt-4o-mini, mesmo orçamento de até 3 chamadas:

| | Reparo guiado (vê o erro do ESBMC) | Amostragem independente |
|---|---|---|
| veredito do ESBMC em até 1 / 2 / 3 chamadas | 3,3% / 8,8% / 12,1% | 3,3% / 4,4% / 4,4% |
| confirmados no código original | 3 | 2 |
| especificações inválidas | 14 | 35 |
| tokens | 346 mil | 354 mil |

**Reparo:** com o mesmo custo, mostrar o erro do ESBMC quase triplica a taxa de verificação em três
tentativas (comparação pedida por Olausson et al., ICLR 2024). Uma rodada por braço; repetir para
medir a variação.

**Confirmação falsa:** nas 107 versões corrigidas dos bugs, **nenhuma confirmação**. Na versão
corrigida de `cli_bool_option`, o ESBMC ainda acusa violação, mas a execução não reproduz: o caso
fica como não validado. A validação por execução evitou um falso positivo real.

---

**Slide 15: Limites do ESBMC-Python documentados**

Série de dez reprodutores mínimos, comparando a versão 8.5.0 com a PR #8014:

- **falsos positivos:** remoção protegida por verificação de lista vazia; método de classe aninhada
  não resolvido;
- **falsos negativos:** soma com valor opcional nulo; atributo de texto opcional (na PR #8014);
- **falhas do verificador:** falha de segmentação com expressão condicional sobre texto opcional;
  exceção sem arquivo nem linha (corrigido na PR #8014); `FAILED` e `UNKNOWN` na mesma execução;
- **construções recusadas:** `async`, fatiamento 2-D do numpy, chamada com `*args`, formatação com `%`.

Cada limite tem o caso do dataset onde apareceu, e todos são candidatos a issue no ESBMC.

---

**Slide 16: Braço experimental com agente**

- Para os casos que o harness automático não alcança, um agente (Claude Code com o plugin ESBMC)
  tenta construir o harness de forma interativa.
- O pipeline não confia no agente: roda o ESBMC por conta própria, reexecuta no CPython e aplica
  a mesma regra de confirmação.
- Se o agente alterar o corpo da função analisada, o resultado é marcado como reescrita e fica
  fora da contagem principal.
- **Pergunta de pesquisa:** quanto um agente interativo recupera além do método automático?

---

**Slide 17: Literatura que fundamenta as decisões**

- **Beyer et al. (TAP 2018):** validação de contraexemplos por execução.
- **Clarke et al. (CAV 2000):** contraexemplos espúrios em abstrações.
- **Olausson et al. (ICLR 2024):** reparo guiado precisa ser comparado com
  amostragem de mesmo custo.
- **Zhang et al. (ISSTA 2024):** drivers gerados por LLM falham em APIs complexas.
- **Amusuo et al. (arXiv 2025, FalseCrashReducer):** drivers gerados produzem
  falhas espúrias por estado irreal.
- **Wu, Barrett e Narodytska (ICLR 2024, Lemur):** a LLM propõe, o verificador decide.

---

**Slide 18: Próximos passos**

**Prioridade alta:**
- Repetir reparo e amostragem 2 a 3 vezes para medir a variação, e rodar o braço do agente nos
  casos restantes.
- Testar o pipeline num repositório Python completo fora do dataset, que é o objetivo final.

**Decisões para discutir:**
1. Usar a localização do gabarito como entrada controlada para a RQ2?
2. Abrir issues no ESBMC-Python com os dez reprodutores?
3. Confirmações que dependem de substituto de biblioteca devem entrar na métrica principal ou ficar
   em uma categoria separada?
