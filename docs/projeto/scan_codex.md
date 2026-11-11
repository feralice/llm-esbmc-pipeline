# Scan com Codex

O pipeline aceita `--backend codex` na detecção e na especificação. Sem `--yes`, o scan apenas monta o grafo e seleciona as funções:

```sh
.venv/bin/python src/main.py --mode scan --input /caminho/do/repositorio \
  --backend codex --scan-limit 20 --output-dir artifacts/scan_codex
```

Para executar a análise, use o mesmo comando com `--yes`. Isso chama o Codex e consome os limites da conta; o custo depende da autenticação e da configuração. `codex login status` mostra o tipo de login. A simulação não testa o acesso ao modelo nem garante que uma rodada real vá funcionar.

O motor de verificação é o padrão. Para usar o modo agente com Codex, acrescente `--scan-verify agent --agent-backend codex`. Sem `--agent-backend codex`, o padrão do agente é Claude. O agente Codex executa `codex exec` na pasta do caso, com as mesmas skills de projeto, consulta ao grafo e registro de chamadas ao ESBMC usados pelo agente Claude. O pipeline ainda verifica e reexecuta o harness por conta própria. Os agentes usam modelos e ferramentas diferentes, portanto não se espera que produzam respostas idênticas. A execução real do agente Codex precisa ser conferida em uma rodada, além dos testes locais com CLI simulada.

No modo agente, trechos de `README`, `doc/` e `docs/` relacionados ao nome da função ou ao módulo são enviados como contexto, com caminho e linha. A busca é limitada e pode não encontrar toda a documentação relevante. O texto é material para conferir contra o código, não uma precondição automática. O conteúdo é identificado no checkpoint: se a documentação mudar, a verificação recomeça e os vereditos anteriores são arquivados.

Para retomar, use a mesma configuração e diretório, acrescentando `--resume`. Não misture uma rodada iniciada com Claude e outra com Codex no mesmo checkpoint sem conferir a compatibilidade das configurações.
