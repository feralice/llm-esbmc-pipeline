# Trabalhos relacionados conferidos (16/10/2026)

Conferidos contra arXiv, Crossref, Semantic Scholar, OpenAlex e páginas das conferências (o DBLP
bloqueou o acesso automático). Títulos exatos. Todos existem e o resumo sustenta a descrição.

| # | Título | Autores | Onde | DOI / arXiv | Relação com este trabalho |
|---|---|---|---|---|---|
| 1 | A New Era in Software Security: Towards Self-Healing Software via Large Language Models and Formal Verification | Tihanyi, Charalambous, Jain, Ferrag, Cordeiro (versão AST) | AST 2025 (com ICSE 2025), pp. 136-147 | 10.1109/AST66626.2025.00020; arXiv 2305.14752 | ESBMC acha a vulnerabilidade em C, o LLM corrige com o contraexemplo. Usa o termo "self-healing" para correção do programa |
| 2 | ESBMC-Python: A Bounded Model Checker for Python Programs | Farias, Menezes, de Lima Filho, Sun, Cordeiro | ISSTA 2024 (demonstração de ferramenta), pp. 1836-1840 | 10.1145/3650212.3685304; arXiv 2407.03472 | O verificador usado aqui |
| 3 | LLM-Assisted Translation and Bounded Model Checking of Python Code | Shivaji, Lobakhina, Havelund, Pinto, Cordeiro (ordem do portal de Manchester; o PDF traz outra ordem) | AISoLA 2025, aceito, ainda não publicado | sem DOI | LLM traduz Python para C e o ESBMC verifica; 23 programas de 15 a 50 linhas com bugs plantados. Trabalho mais próximo, do grupo do orientador |
| 4 | PyVeritas: On Verifying Python via LLM-Based Transpilation and Bounded Model Checking for C | Orvalho, Kwiatkowska | só arXiv | arXiv 2508.08171 | LLM traduz Python para C, CBMC e localização de falha por MaxSAT |
| 5 | Python Symbolic Execution with LLM-powered Code Generation | Wang, Liu, Chen, Li, Jin, Huang, Ma | só arXiv | arXiv 2409.09271 | LLM gera código Z3 para restrições de caminho em Python (LeetCode) |
| 6 | Large Language Model Powered Symbolic Execution | Li, Meng, Duck | OOPSLA 2025 (PACMPL 9, OOPSLA2), pp. 3148-3176 | 10.1145/3763163 | LLM raciocina sobre restrições de caminho, sem SMT (AutoBug) |
| 7 | Nagini: A Static Verifier for Python | Eilers, Müller | CAV 2018, LNCS, pp. 596-603 | 10.1007/978-3-319-96145-3_33 | Verificador estático de Python tipado com contratos, sem LLM |
| 8 | Agentic Model Checking | Sun, Liu, Kroening, Xue | só arXiv (2026) | arXiv 2605.21434 | Agentes LLM propõem especificações a partir dos chamadores, BMC decide (C/Rust) |
| 9 | HarnessLLM: Rust Verification Harness Generation with Large Language Models | Wang, Liu, Huang | ICSE 2026 | 10.1145/3744916.3773122; arXiv 2607.22161 | LLM gera harness de verificação a partir dos testes existentes (Rust) |
| 10 | The Hitchhiker's Guide to Program Analysis, Part III: Mostly Harmless LLMs | Li, Zhou, Sridharan, Zhang, Qian | só arXiv (2026) | arXiv 2606.15122 | Evident: LLM só monta o harness, backend formal decide (drivers Android) |
| 11 | Verified Code Transpilation with LLMs | Bhatia, Qiu, Hasabnis, Seshia, Cheung | NeurIPS 2024, pp. 41394-41424 | 10.52202/079017-1310; arXiv 2406.03003 | LLM traduz para uma DSL e prova equivalência formalmente |

Cuidados ao citar:
- 1: na versão AST são 5 autores (sem Youcheng Sun), em ordem diferente da do arXiv.
- 3: citar como "a aparecer"; conferir a ordem dos autores na versão final. Vale perguntar ao Lucas.
- 4, 5, 8, 10: citar como preprint do arXiv.
- 9: citar a versão do ICSE 2026, não o arXiv.

Diferença defensável deste trabalho: bugs reais de projetos reais, verificação do Python original (sem
tradução para C) e confirmação concreta no código original. Os mais próximos (3 e 4) traduzem para C e usam
programas pequenos.
