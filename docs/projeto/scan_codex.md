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


## Contexto estático do repositório (opcional)

`--scan-repository-context evidence` acrescenta evidências com origem à detecção e à especificação
do motor; também funciona no verificador agente. O padrão `off` preserva o comportamento e os
fingerprints anteriores. A opção `evidence` é exclusiva do scan e é rejeitada em hybrid/benchmark
antes de criar saídas ou chamar modelos.

O parser YAML é uma dependência opcional do pipeline: instale `requirements-scan-context.txt`
somente no ambiente reservado à nova rodada. Não instale dependências do repositório alvo.

```sh
PYTHONPATH=src .venv/bin/python src/main.py --mode scan --input /caminho/do/repositorio \
  --backend codex --agent-backend codex --scan-limit 5 \
  --scan-repository-context evidence --scan-smells --no-auto-lessons --heal none \
  --output-dir artifacts/scan_contexto_novo
```

Sem `--yes`, esse comando não chama a LLM e permite conferir `scan_repository_context.json`.
Com `--yes`, consome a assinatura; faltas de parser/configuração devem ser resolvidas antes disso.
`--heal none` é uma escolha dessa rodada, não uma mudança do padrão de reparos.

O suporte inicial associa handlers a configurações SAM locais e literais (`CodeUri`, `Handler`,
eventos `Api`, rota e método), distingue handlers com o mesmo nome e encontra trechos relacionados
de README/doc/docs e exemplos JSON de eventos. A configuração desconhecida, customizada ou com
múltiplas entradas fica explicitamente sem contrato estabelecido. Não resolve `!Ref`, `!Sub`, macros,
URLs de código nem executa o alvo. A referência ao formato proxy padrão é condicional à integração
declarada: não prova que toda chamada direta à função tenha esse formato.

A coleta tem limites de 2.000 arquivos, 128.000 bytes por arquivo, 40 níveis e 10.000 nós YAML;
cada função recebe até quatro trechos em um bloco de até 4.800 caracteres. São limites de tamanho,
não uma garantia de custo em tokens. Arquivos ignorados, erros, ambiguidades e truncamentos são
registrados. Links simbólicos e caminhos fora da raiz não são lidos.

Os exemplos não se tornam precondições universais. O coletor não acrescenta suposições ao harness,
não descarta hipóteses e não altera o significado de `CONFIRMED`. A LLM recebe evidência não confiável
para conferir; a avaliação do contrato do projeto continua separada do veredito do programa gerado.

O arquivo de contexto guarda hash, inventário e origem dos trechos. Distingue despacho à detecção,
fornecimento ao verificador e uma tentativa de especificação que retornou com o contexto registrado.
Esses registros não provam que o modelo interpretou corretamente a evidência. Em retomada, o mesmo
contexto preserva o histórico de envio; contexto diferente muda os fingerprints e impede mistura
silenciosa. Um snapshot anterior é arquivado antes de ser substituído.


Na associação SAM, `CodeUri`/`Handler` literais herdados de `Globals.Function` são considerados com
sua origem. Uma definição de API global não resolvida ou uma `FunctionUrlConfig` adicional (local
ou herdada) impede a afirmação de contrato único. O provedor usa o arquivo e nome qualificado
registrados no grafo, inclusive para raízes de pacotes e módulos `__init__.py`. O limite do bloco
é conferido depois da serialização/escape; o JSON permanece legível e o truncamento é persistido.
