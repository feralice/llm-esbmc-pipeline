# Prompt para segunda opinião (outra LLM)

Copiar tudo abaixo da linha.

---

Sou mestranda em verificação de software. Quero uma segunda opinião técnica e crítica sobre um
problema de pesquisa. Responda em português, seja direto e diga quando achar que estou no caminho
errado.

## O projeto

Pipeline que detecta bugs de runtime em código Python real e os confirma por verificação formal:

1. Um LLM lê uma função Python real e aponta um possível bug (linha, expressão, condição de disparo).
2. Um harness é montado **por código** (não pelo LLM): a função é recortada do módulo, as entradas viram
   valores não determinísticos (`nondet_int()`, `nondet_str()` etc.), chamadas a bibliotecas viram stubs.
   O LLM só devolve um JSON com os tipos das entradas e dos stubs.
3. O ESBMC-Python (model checker limitado, https://github.com/esbmc/esbmc, frontend em
   `src/python-frontend/`, modelos Python em `src/python-frontend/models/`) procura uma entrada que
   quebre a função.
4. Um replay em CPython roda a função **original** com essa entrada; o bug só conta se o CPython levanta
   a mesma exceção na linha do bug.

Dataset: 289 bugs reais (BugsInPy e repositórios conhecidos: pandas, keras, youtube-dl, thefuck, luigi,
scrapy, matplotlib, ansible, tornado...), com gabarito da linha do bug tirado do patch de correção.
ESBMC v8.6.

## O problema principal

Fazer o ESBMC aceitar código Python real. Na última rodada completa (564 hipóteses em 230 bugs):

| Onde parou | Hipóteses | Bugs |
|---|---|---|
| ESBMC recusou o programa (feature não suportada) | 185 | 102 |
| Limite de uso do LLM (não técnico) | 114 | 56 |
| Não foi possível montar o harness (recorte da função) | 72 | 39 |
| Dependência externa sem modelo (numpy, pandas, tf...) | 74 | 31 |
| ESBMC deu veredito, sem confirmação no replay | 71 | 44 |
| Tipos rejeitados, timeout ou erro interno do ESBMC | 24 | 16 |
| **Confirmado** | **24** | **19** |

As 185 recusas são de 62 tipos diferentes, quase todos em 1 a 4 bugs (cauda longa). Os mais comuns:

- `Variable 'args' is not defined in function 'Network'` (20 hipóteses, 9 bugs), com `*args` usado
  dentro do corpo;
- `Could not resolve type of receiver in member call '.path_params.copy()'` (13, 9): cadeia de atributos
  sem tipo;
- `NameError: name 'IOError' is not defined` (7, 4): builtin ausente nos modelos;
- `Type inference failed for Assign` (7, 4), por exemplo `old_codes = (...)` multilinha;
- `enumerate() with a nested unpacking target is unsupported` (6, 2);
- `fancy indexing with a non-boolean array is not supported` (5, 1);
- classe com `__new__` próprio (7, 5).

Outra limitação: o contraexemplo do ESBMC não mostra o valor de um `nondet_str()` (só um ponteiro);
contornei copiando cada caractere para um `int` e rodando com `--no-slice`.

## O que já foi feito

- 12 regras de reescrita do código antes do ESBMC (ex.: proteção explícita para `None` em
  aritmética, `%` de formatação, `@property` como atributo, decoradores do projeto removidos), cada uma
  com programas-sonda: a regra só é aplicada se o ESBMC instalado ainda falha na sonda (adaptação
  automática à versão).
- Laço de reparo: erro do ESBMC volta ao LLM para corrigir os tipos (até 3 tentativas).
- Contexto dos chamadores no pedido de tipos, e rejeição de tipo contraditório pelo uso.
- Escalada de limites (unwind 5, 10, 20, incremental) e troca de solver em timeout.
- Braço "agente": o LLM escreve o harness livremente, checado contra os mesmos critérios.
- Braço dinâmico (busca de entradas em CPython) para comparação.
- Variantes de prompt de detecção (few-shot por similaridade, citação obrigatória da linha).
- Oráculo de valor para bugs de resultado errado (pós-condição escrita pelo LLM, controle com a versão
  corrigida).

## Restrições

- Prazo: qualificação até fevereiro de 2027.
- LLMs disponíveis: Gemini (grátis, com limite diário), Claude e Codex por assinatura com limite;
  pouco orçamento de API. GPU de 6 GB (fine-tuning local é inviável).
- Meu orientador é um dos líderes do ESBMC, então corrigir o próprio frontend é uma opção real.

## O que quero de você

1. Estou atacando o problema certo? A recusa do ESBMC é o gargalo, ou o gargalo real está em outro
   lugar (por exemplo no recorte da função ou nas dependências)?
2. Que técnicas (com LLM ou sem) você usaria para aumentar a fração de código real que o ESBMC aceita?
   Considere: reescrita da linha recusada por LLM validada por testes diferenciais, tradução para um
   subconjunto verificável, modelos/stubs gerados para bibliotecas, contribuir correções ao frontend,
   recorte mais agressivo (só o caminho até a linha do bug), ou outra coisa.
3. Para cada técnica: custo, risco de falso positivo e quanto acha que move o número de bugs confirmados.
4. Vale mais tentar subir o número de 24 confirmações, ou transformar o mapa das recusas (62 tipos e
   quantos bugs cada um bloqueia) numa contribuição da dissertação, como estudo empírico das limitações
   da verificação formal de Python real?
5. Há trabalhos publicados que já atacaram isso (LLM + model checking/verificação formal em Python ou
   outra linguagem dinâmica)? Se citar, diga só o que tem certeza que existe e marque o que não tem
   certeza; eu vou conferir cada referência.
6. O que você faria nas próximas 4 semanas no meu lugar?
