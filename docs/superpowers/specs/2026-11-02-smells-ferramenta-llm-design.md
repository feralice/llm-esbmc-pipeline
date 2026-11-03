# Smells: a ferramenta gera candidatos, o LLM filtra e explica

Data: 02/11/2026. Item "Code smells: linter gera os candidatos e o LLM filtra e explica" da seção Depois do
`docs/projeto/PLANO_2026-10-19.md`, puxado antes da tag `v2-congelado-2026-11b` por decisão da Fernanda.

## Por quê

Ferramenta de smell acha quase tudo e erra muito. No PySmell rotulado à mão (`dataset/code_smell/pysmell_manual.jsonl`,
2570 itens, 150 smells), as duas heurísticas da própria ferramenta, juntas, apontam 1056 itens: 139 smells reais
(recall 93%) e 917 alarmes falsos (precisão 13%). Medido em 02/11 a partir dos campos `tool_experience_based` e
`tool_statistics_based` do arquivo.

O iSMELL (Wu et al., ASE 2024, DOI 10.1145/3691620.3695508, conferido no Crossref) junta ferramentas
especialistas com LLM: a ferramenta detecta e a saída dela entra no prompt, e o LLM decide e explica. A pergunta
aqui é a mesma: o LLM tira os falsos sem perder os reais?

Smell é manutenção, não bug: nada daqui vai ao ESBMC, e o resultado fica fora das métricas de detecção de bug.

## Objetivos

1. **Filtro**: para cada candidato (smell, arquivo, linha, ferramenta que apontou, métricas da ferramenta,
   trecho do código), o LLM responde JSON `{"smell": bool, "reason": str}` com a definição do smell no prompt.
   Prompt em inglês, como a detecção congelada.
2. **Medição no PySmell**: candidatos = os itens que a ferramenta apontou; comparar ferramenta sozinha com
   ferramenta + LLM em precisão, recall e F1 por smell, contra os rótulos humanos.
3. **Repo real**: no scan, candidatos vindos do `ruff` (regras de tamanho e complexidade mapeadas para os nomes
   de smell) passam pelo mesmo filtro e saem numa seção "smells (exploratório)" do relatório, já que ali não há
   gabarito.

## Fora do escopo

- Refatoração automática (o iSMELL também refatora; aqui não).
- Smells de ML (mlflow, CodeSmile) e o Smelly Code: ficam para depois; o PySmell é o único com negativos rotulados
  em quantidade e saída da ferramenta no próprio arquivo.
- Instalar pylint: o ruff já está no ambiente e cobre as regras de tamanho e complexidade.

## O que não pode acontecer

- Número de precisão ou recall sem os candidatos que o LLM não respondeu: JSON inválido ou falha da sessão conta
  à parte e aparece no relatório, nunca some do denominador.
- Rodada com LLM sem autorização: a medição gasta a assinatura (`claude_cli`); só roda com o ok da Fernanda.

## Decisões de desenho

- Candidatos do PySmell = a união das duas heurísticas (onde está o recall de 93%); o filtro só pode tirar.
- Os candidatos do mesmo trecho de código vão numa chamada só, para gastar menos (cerca de 1056 candidatos em
  bem menos chamadas). Cada candidato tem id próprio na resposta.
- Primeira rodada: sorteio de 200 candidatos, semente 42, uma repetição; rodada completa só se a primeira mostrar
  ganho.
- Mapeamento do ruff: PLR0913 → LongParameterList; PLR0915 e C901 → LongMethod; PLR0904 → LargeClass. Os demais
  smells do PySmell (cadeia de mensagens, lambda longa, compreensão complexa) não têm regra no ruff e não entram
  no scan.

## O que fica para quem implementa

- Onde o módulo mora (sugestão: `src/research_pipeline/smells/`) e os nomes.
- Definições dos 10 smells no prompt, a partir do artigo do PySmell e do catálogo do próprio repositório.
- Testes com LLM falso: JSON válido, inválido, candidato faltando na resposta, lote misturado.
