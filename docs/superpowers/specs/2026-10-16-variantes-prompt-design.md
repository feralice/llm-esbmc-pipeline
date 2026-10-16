# Variantes de prompt (item 4 do PLANO_GERAL)

Data: 16/10/2026. Item 4 de `docs/projeto/PLANO_GERAL_2026-10-15.md`. Este documento cobre só a
implementação. A comparação entre variantes roda no item 6, com o gabarito já corrigido (item 1), e
nenhuma chamada a LLM acontece aqui.

## Objetivo

Na rodada final de 15/10, em 44 bugs de exceção o LLM acertou a função e apontou outra expressão. Parte
disso é rótulo (o gabarito só aceitava uma expressão; o item 1 acrescenta `cause_expressions` e
`crash_expressions`), parte é erro real do LLM. Exemplo: em `bip_pandas_84` o gabarito é
`index._get_level_number(i)` e o LLM apontou `index.levels[i]`, uma leitura que vem depois, na linha
seguinte.

O item entrega duas variantes novas, compostas com A5 (`--v2-variants A1,A2`), mais um caminho para
inspecionar os prompts sem chamar LLM, e deixa o Gemini (`--backend google`, sem custo) pronto para rodar
a comparação depois:

- **A13, exemplos reais por similaridade:** k bugs reais do próprio gabarito, escolhidos pela semelhança
  com a função analisada, nunca do mesmo projeto (deixa um projeto de fora).
- **A14, evidência citada:** cada achado traz a linha copiada da função e a condição sobre as entradas
  que dispara o erro; sem as duas, o achado não é reportado.

Base de leitura (já conferida em `docs/projeto/fichamento.md`, linhas 42, 50 e 51): Hannan et al. (NDSS
2026) sobre a escolha de exemplos few-shot por similaridade em detecção de vulnerabilidades; Fahad et al.
sobre prompts de raciocínio guiado por evidência; PromptAudit sobre a sensibilidade do resultado a
mudanças pequenas no prompt, que justifica medir uma mudança por vez.

## Como as variantes funcionam hoje

| Peça | Onde | O que importa para este item |
|---|---|---|
| Composição | `src/research_pipeline/llm/prompt_variants.py:115-120` | `apply_variants` aplica em ordem e recusa nome desconhecido. |
| Âncoras | `prompt_variants.py:11-14` | `_swap` falha alto quando o trecho âncora some do prompt base. |
| Registro | `prompt_variants.py:108-112` | Dicionário `VARIANTS`, de A1 a A12 (sem A4 e A5, que são combinações). |
| Causa e quebra | `prompt_variants.py:65-80` | A9 já pede `crash_expression` separado de `expression`. |
| Prompt de sistema | `src/research_pipeline/llm/prompts.py:55-66` | `load_system_prompt` com `lru_cache`, aplica as variantes ao `system_prompt_v2.txt`. |
| Prompt do usuário | `prompts.py:83-103` | Variantes que dependem da função (A10, A11, A12) entram aqui. |
| Função limpa | `prompts.py:126-151` | `_source_for_llm` troca o nome por `target_function` e tira a docstring. |
| Estado global | `prompts.py:167-173` | `set_context_sources` é o padrão para configuração de A11. |
| Esquema | `src/research_pipeline/llm/schema.py:104-115` | `v2_findings_schema` acrescenta campos por variante (A7, A9). |
| Leitura da resposta | `src/research_pipeline/llm/findings.py:38-82` | `finding_from_dict` só guarda os campos que conhece; o resto se perde. |
| Divisão de A9 | `findings.py:111-116` | Quebra diferente da causa vira um segundo achado (origem do ruído de A9). |
| Gemini | `src/research_pipeline/llm/backends/factory.py:68-77`, `chat_completions.py:49-58` | API compatível com OpenAI, `json_object` sem esquema, 4 s entre chamadas, modelo padrão `gemini-2.5-flash` (`factory.py:18`). |
| CLI | `src/main.py:302-307`, `1191`, `1228-1241` | `--v2-variants` vira tupla e vai ao `build_analyzer`; `set_context_sources` logo depois. |
| Impressão digital | `main.py:489-503` | Hash do `system_prompt_v2.txt` e do esquema; os arquivos `v2_variants/*.txt` não entram. |
| Avaliação | `src/research_pipeline/v2_evaluator.py:79-85`, `126-159`, `193-206` | Compara só a `expression` de cada candidato com `expression`, `cause_expressions` e `crash_expressions` do gabarito. |
| Candidato | `src/research_pipeline/verify/candidate.py:11-18` | Guarda arquivo, função, expressão, nota e propriedade; outros campos de `metadata` não chegam ao relatório. |
| Rodadas | `scripts/run_detection_variants.sh:18-22` | Backend fixo em `claude_cli`. |

A rodada final pausada (`artifacts/v2/final-2026-10-15-codex`, 470/564) usa A1,A2 e tem impressão digital
com as chaves `config`, `sources`, `detector_prompt`, `detector_schema` e `spec_prompt`. Ela precisa
continuar retomável no item 6.

## A opção (a) já existe

Pedir separadamente a linha da causa e a da quebra é exatamente o A9. Na fase 11 (12/10) ele deu linha 25
contra 24 do A5 e quase dobrou o ruído (121 contra 72), porque cada quebra distinta vira um achado a mais.
Com o gabarito novo, que aceita causa e quebra, o A9 pode medir outra coisa; por isso entra na comparação
do item 6 como está, sem reimplementação.

## Variante A13: exemplos reais por similaridade

### Texto no prompt de sistema (antes de `## SAÍDA: JSON válido`)

```
## EXEMPLOS DE BUGS REAIS

Depois da função vem um bloco `UNTRUSTED_EXEMPLOS` com funções de outros projetos
e o bug real que os mantenedores corrigiram em cada uma: a expressão que a correção
mudou e, quando houve exceção, onde ela estoura. Use-os para calibrar que expressão
apontar em `expression`. Eles não são a função analisada: não reporte achados sobre
eles e não suponha que a função analisada tenha o mesmo bug.
```

### Bloco no prompt do usuário (depois de A11 e A12, antes do aviso final)

```
<UNTRUSTED_EXEMPLOS>
Exemplo 1:
def target_function(values, i):
    return values[i + 1]
Bug corrigido pelos mantenedores: `values[i + 1]`
Onde a exceção estoura: `values[i + 1]`
Efeito: IndexError com lista de um elemento
verifiable: true

Exemplo 2:
...
</UNTRUSTED_EXEMPLOS>
```

A linha "Onde a exceção estoura" só aparece quando o exemplo tem `crash_expressions` (a primeira). O
"Efeito" é o `failure_kind_note` do item, cortado em 200 caracteres; sem nota, uma frase fixa por
`failure_kind`. `verifiable` vem de `should_reach_esbmc` (`v2_evaluator.py:30-37`), a mesma regra da
avaliação de triagem. A função de exemplo passa pela mesma limpeza da função analisada
(`_source_for_llm`), e o nome original dela também é trocado por `target_function` dentro das expressões.

### Pool de exemplos

- Fonte: `dataset/bugs_reais/ground_truths.json` (lido em tempo de execução, então pega as correções do
  item 1) e as funções em `dataset/bugs_reais/funcao_com_bug/<file>`.
- Entram itens com `failure_kind` conhecido e diferente de `incerto`, com `expression` preenchida e
  com função de até 2.500 caracteres. Hoje entram 227 dos 289 (conferido com `preprocess_file`;
  todos os 289 têm a função localizável).
- Similaridade: Jaccard entre conjuntos de símbolos da função (nomes, atributos, parâmetros e os tipos de
  nó do AST menos comuns, como `Subscript`, `BinOp`, `Raise`). Sem embedding: não custa chamada nenhuma e
  é determinística. Empate desfeito pelo `id`, então duas rodadas veem os mesmos exemplos.
- `k` padrão 3 (`--example-k`). Três funções de até 2.500 caracteres somam no máximo cerca de 2 mil tokens
  por chamada, dentro do que o plano gratuito do Gemini aguenta.

### Prevenção de vazamento

- A função analisada é identificada pelo nome do arquivo (`funcao_com_bug/<id>.py`, e `file == id + ".py"`
  para os 289). Saem do sorteio o próprio item e **todos os itens do mesmo projeto**
  (`provenance.project`), porque o mesmo bug aparece em mais de um id (ex.: `av_real_01` e os
  `bip_youtube_dl_*` vêm do youtube-dl) e funções do mesmo arquivo compartilham contexto.
- O projeto da função analisada vem de um índice com todos os 289 itens, inclusive os que não entram no
  pool (incertos e longos), para que a exclusão valha para qualquer bug.
- Fora do gabarito (modo scan), o arquivo não é conhecido: só a similaridade decide. O A13 não faz parte do
  padrão do scan (`scan/pipeline.py:30`) e fica fora do escopo dele.
- Sem pool configurado, pedir A13 levanta `ValueError`: nunca cai em silêncio para um prompt sem exemplos.

## Variante A14: evidência citada

### Texto no prompt de sistema (antes de `## SAÍDA: JSON válido`)

```
## EVIDÊNCIA CITADA

Para cada achado, preencha mais dois campos em `metadata`:
- `quoted_line`: a linha inteira da função onde está `expression`, copiada sem
  mudar nada; `expression` precisa aparecer dentro dela;
- `trigger`: a condição concreta sobre as entradas ou o estado que leva ao
  comportamento errado, escrita como expressão Python sobre os nomes da função
  (por exemplo `len(xs) == 0` ou `k > len(scores)`).
Se não conseguir copiar a linha ou escrever a condição, não reporte o achado.
```

### Mudança no JSON de exemplo do prompt

Depois de `"line": 0,` entram:

```
        "quoted_line": "<linha inteira copiada da função>",
        "trigger": "<condição sobre as entradas que leva ao erro>",
```

## Compatibilidade com o esquema de saída

- `v2_findings_schema` ganha `quoted_line` e `trigger` (strings, obrigatórias) em `metadata` quando A14 está
  na lista, como já faz com `crash_expression` para A9. Para A1,A2 e para A9 sozinho o esquema fica
  idêntico, então o hash `detector_schema` da rodada pausada não muda.
- `finding_from_dict` passa a guardar `quoted_line` e `trigger` (vazios quando ausentes). O Gemini usa
  `json_object` sem esquema: o texto do prompt é a única cobrança, e um achado sem os campos continua
  válido.
- A13 não muda o formato da resposta.
- A avaliação não muda: ela lê só a `expression` de cada candidato. A14 e A13 agem sobre qual expressão o
  LLM escolhe, não sobre como ela é comparada.
- Impressão digital: só quando A13 ou A14 estão na lista entram `detector_system_prompt` (hash do prompt de
  sistema já composto) e, com A13, `example_pool` (hash do gabarito usado como pool); `config` ganha
  `example_pool` e `example_k` só com A13. Assim, mudar o pool ou o texto da variante impede retomar uma
  rodada com prompt diferente, e a rodada A1,A2 pausada continua retomável.

## Inspeção sem LLM

`scripts/print_detection_prompt.py` monta o prompt de sistema e o prompt do usuário de cada função com as
mesmas funções do pipeline (`load_system_prompt`, `build_user_prompt`) e imprime, ou grava um arquivo por
função com `--out`. No fim informa o total estimado de tokens de entrada (caracteres / 4), para comparar o
tamanho das variantes antes de gastar cota. Não constrói nenhum analisador.

`scripts/run_detection_variants.sh` passa a ler `BACKEND` e `MODEL` do ambiente (padrão `claude_cli` e
`claude-sonnet-5-5`), para o item 6 rodar com `BACKEND=google MODEL=gemini-2.5-flash` sem editar o script.

## Testes

- A14: texto e posição no prompt, campos no esquema, composição com A9 no esquema, campos preservados por
  `finding_from_dict` quando o backend não tem esquema.
- Pool: incertos e funções longas ficam de fora; rótulo e efeito corretos; nunca o próprio bug nem o mesmo
  projeto; o mais parecido vem primeiro; empate pelo `id` e resultado igual em duas chamadas; arquivo fora
  do gabarito só ordena por similaridade.
- A13: bloco de exemplos só com outros projetos, nome original trocado por `target_function`, erro alto
  sem pool, nada de exemplo quando A13 não foi pedido.
- CLI: A13 carrega o pool e registra `example_pool` e `example_k`; pool inexistente sai com código 1;
  impressão digital de A1,A2 com exatamente as cinco chaves de hoje.
- Inspeção: imprime os dois prompts, grava um arquivo por função, não toca rede nem subprocesso.
- Composição A1,A2,A9,A13,A14 e suíte completa.

## Fora do escopo

- Qualquer chamada a LLM, rodada ou comparação entre variantes: tudo isso é o item 6.
- Escolher o prompt final.
- Mudar a avaliação, inclusive o ruído de A9 que conta a quebra como achado à parte.
- Levar `quoted_line` e `trigger` para o candidato e o relatório (hoje só a `expression` chega lá).
- Checar por código se `quoted_line` existe na função e descartar o achado quando não existe.
- Embedding para similaridade; pool fora de `dataset/bugs_reais`; A13 no modo scan.
- Corrigir a impressão digital para os arquivos `v2_variants/*.txt` de A2, A8 e A12 (lacuna anterior; mexer
  agora quebraria a retomada da rodada pausada).

## Decisões tomadas sem a Fernanda

1. **A opção (a) não vira variante nova:** é o A9, que já existe e foi medido; ele só entra na lista do
   item 6.
2. **Duas variantes, não três:** A13 e A14. Uma terceira só faria sentido como outra formulação de causa e
   quebra, o que repetiria o A9.
3. **Exclusão por projeto inteiro**, não só pelo id: o mesmo bug aparece com ids diferentes no gabarito.
4. **Similaridade lexical por AST (Jaccard)**, sem embedding: zero custo, determinística e reproduzível;
   Hannan et al. usam similaridade, não necessariamente esta.
5. **k = 3 e funções de até 2.500 caracteres**, pensando no limite do plano gratuito do Gemini.
6. **Exemplos sem JSON completo:** o gabarito não tem `explanation`, `operands` nem `guard_evidence`;
   inventar esses campos seria fabricar rótulo. O exemplo mostra só o que o gabarito sabe.
7. **Exemplos de resultado errado também entram**, com `verifiable: false`, porque 178 dos 289 bugs são
   desse tipo e o pool precisa refletir isso.
8. **A14 só pede e guarda os campos**; não descarta achado por código. Descartar seria uma terceira
   mudança, que PromptAudit recomenda medir em separado.
9. **Impressão digital ampliada só para A13 e A14**, para não invalidar o checkpoint da rodada pausada.
10. **Pool padrão é o `ground_truths.json` do repositório**, trocável por `--example-pool`.
