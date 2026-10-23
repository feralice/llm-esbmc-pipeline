# Dúvidas para a reunião com Lucas e Rosie (30/09/2026)

## Método da dissertação

1. **Localização do gabarito na RQ2.** Usar a função e a expressão do gabarito como entrada
   controlada, para medir a verificação separada da detecção, é aceitável como desenho experimental?
2. **Métrica principal da detecção.** Expressão equivalente (40%) como principal, com a de texto
   idêntico (20%) ao lado, ou o contrário?
3. **Confirmações que passam por substituto de biblioteca.** Entram na contagem principal ou ficam
   numa categoria separada, "confirmado com substituto"?
4. **Próximo passo para os substitutos.** Qual caminho vale mais para a dissertação:
   a. a LLM descrever o comportamento da biblioteca no JSON (ex.: `sys.exit` nunca retorna);
   b. conferir a execução com a biblioteca real instalada, quando possível;
   c. os dois?
5. **Braço com agente.** Os 4 casos que ele confirmou, onde o motor parava, entram como contribuição
   da dissertação ou só como experimento exploratório? O uso de um agente comercial é um problema?
6. **Troca de solver.** Adotar Boolector quando o Bitwuzla estoura o tempo (resolveu 2 de 7 casos)
   é uma decisão aceitável, ou há motivo para manter um solver fixo?
7. **Code smells.** Ainda devo focar neles (por exemplo, como sinal para escolher quais funções a
   LLM analisa num repositório grande) ou a dissertação fica só em bugs que causam falha na
   execução?

## ESBMC-Python

8. **Issues.** Posso abrir issues com os reprodutores dos limites encontrados (falso positivo com
   `pop` protegido, falso negativo com `Optional[int]`, `SystemExit` ausente, `%d` não constante,
   entre outros)? Alguém do grupo já trabalha nesses pontos?
9. **Limite do verificador.** Os casos destravados pelo harness param no próximo limite do ESBMC.
   Faz sentido a dissertação contribuir com correções no frontend Python, ou o foco deve ficar no
   pipeline?

## Dataset

10. **Candidatos novos.** Incorporar os 199 bugs validados por mantenedores (BugsInPy) passando pelos
   mesmos portões (build e teste que falha)? Existe um tamanho mínimo esperado para a qualificação?
11. **Repositório real.** Há um repositório Python que vocês sugiram para o teste de ponta a ponta
    fora do dataset?

## Qualificação (até fevereiro de 2027)

12. **Recorte.** O que já existe (detecção, verificação com execução, controles, limites
    documentados) basta como núcleo da qualificação? O que falta de indispensável?

## Disciplina PGENE601

13. **Tema.** Posso usar o próprio pipeline, aplicado a software Python ciber-físico, ligado ao
    tópico 15 (ESBMC-Python) e aos tópicos 32 e 33?
14. **Domínio.** Bibliotecas como pymodbus, python-can, pymavlink e drivers CircuitPython contam como
    software ciber-físico para a disciplina, ou é preciso código C embarcado?
15. **Grupo.** Faço sozinha ou há alguém do grupo com tema próximo para formar dupla?
16. **Extensões.** Vale incluir a pós-condição a partir da docstring (ideia do artigo 33) ou o
    reparo com ESBMC-AI (artigo 32), ou é melhor manter o escopo menor?
