"""Argument declarations and validation for the public CLI."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from .verify.healing import HEAL_MODES

REPO_ROOT = Path(__file__).resolve().parents[2]

def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("deve ser um inteiro maior ou igual a 1")
    return parsed

def _review_score(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 10:
        raise argparse.ArgumentTypeError("deve estar entre 0 e 10")
    return parsed

class _CommandWords(argparse.Action):
    """argparse reads a word starting with ``-`` as an option, so flags for ESBMC arrive quoted in one word."""

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) == 1 and not Path(values[0]).exists():
            values = shlex.split(values[0])
        setattr(namespace, self.dest, values)

# Option values a profile sets; an option the user passed explicitly keeps the user's value.
PROFILES: dict[str, dict] = {
    "rapido": {"heal_triage": True, "heal_rounds": 1, "workers": 4},
    "padrao": {},
    "medicao": {"auto_lessons": False, "operational_retries": 2, "workers": 1},
}


class _ProfileParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        parsed = super().parse_args(args, namespace)
        for dest, value in PROFILES.get(parsed.profile or "padrao", {}).items():
            if getattr(parsed, dest) == self.get_default(dest):
                setattr(parsed, dest, value)
        return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = _ProfileParser(
        description="Pipeline LLM + AST + ESBMC para análise de bugs em Python.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default=None,
        help="Conjunto de opções: rapido (reparo com teto de 1 rodada e triagem), padrao (nada muda) ou medicao "
             "(lições automáticas desligadas e retentativa operacional). Uma flag passada com o valor padrão não vence o perfil.",
    )
    parser.add_argument(
        "--mode",
        choices=["hybrid", "benchmark", "scan"],
        default="benchmark",
        help="Modo de execução. (padrão: benchmark)",
    )
    parser.add_argument(
        "--input", "-i",
        nargs="+",
        required=True,
        metavar="CAMINHO",
        help=(
            "Arquivo(s) Python ou diretório. Diretórios são lidos recursivamente. "
            "No modo scan, um único diretório de repositório."
        ),
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        metavar="DIR",
        help="Diretório de saída para relatórios e artefatos.",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODELO",
        help=(
            "Modelo LLM a usar. "
            "Valores: 'gpt', 'claude', 'deepseek' ou nome completo como "
            "'gpt-5.5', 'claude-opus-4-8', 'deepseek-r1:7b'. "
            "(padrão: gpt-5.5)"
        ),
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "anthropic", "ollama", "google", "codex", "claude_cli"],
        default=None,
        help="Backend LLM. Inferido automaticamente do --model se omitido.",
    )
    parser.add_argument(
        "--synth-backend",
        choices=["openai", "ollama", "google", "codex", "claude_cli", "anthropic"],
        default=None,
        help=(
            "Backend só para a síntese de harness no modo V2 (padrão: mesmo de --backend). "
            "'google' usa a API compatível do Gemini; 'codex' chama o `codex exec` local via assinatura já paga, em vez da API "
            "OpenAI cobrada por token; 'claude_cli' chama `claude -p` local via assinatura Claude já paga, sem precisar de "
            "OPENAI_API_KEY/GEMINI_API_KEY."
        ),
    )
    parser.add_argument(
        "--synth-model",
        default=None,
        metavar="MODELO",
        help="Modelo só para a síntese de harness no modo V2 (padrão: mesmo de --model).",
    )
    parser.add_argument(
        "--bound",
        type=_positive_int,
        default=20,
        help="Bound de unwinding para o ESBMC (teto do --max-k-step incremental). (padrão: 20)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=60,
        help="Timeout em segundos para cada chamada ao ESBMC. (padrão: 60)",
    )
    parser.add_argument(
        "--llm-timeout",
        type=_positive_int,
        default=300,
        help="Timeout em segundos para chamadas à API da LLM. (padrão: 300)",
    )
    parser.add_argument(
        "--esbmc-command",
        nargs="+",
        action=_CommandWords,
        default=None,
        metavar="CMD",
        help="Comando ESBMC customizado; flags vão entre aspas, ex: --esbmc-command \"esbmc --python python3\"",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=None,
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
    )
    parser.add_argument(
        "--google-api-key",
        default=None,
    )
    parser.add_argument(
        "--ollama-base-url",
        default=None,
    )
    parser.add_argument(
        "--report",
        default=None,
        metavar="CAMINHO",
        help=(
            "Caminho do relatório JSON de saída. "
        ),
    )
    parser.add_argument(
        "--ground-truth",
        default=None,
        metavar="CAMINHO",
        help=(
            "Ground truth para comparação (obrigatório no modo benchmark). "
            "Informe dataset/bugs_reais/ground_truths.json; "
            "ele é lido somente depois das chamadas às LLMs e ao ESBMC."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Retomar unidades concluídas no --output-dir; exige a mesma "
            "configuração de modelo, prompt, bound e timeout."
        ),
    )
    parser.add_argument(
        "--agent-fallback",
        action="store_true",
        help="Motor verify: quando o harness determinístico não chega a um veredito do ESBMC, tenta o "
             "agente (Claude Code + plugin ESBMC, assinatura do Claude Code); o resultado é refeito pelo pipeline.",
    )
    parser.add_argument(
        "--agent-backend", default="claude", choices=["claude", "openai", "google", "ollama", "claude_cli", "codex", "anthropic"],
        help="Agente do nível 2: 'claude' é o Claude Code com o plugin ESBMC; os outros fazem o mesmo ciclo por API "
             "(qualquer pessoa reproduz sem assinatura do Claude; 'ollama' usa modelo local).",
    )
    parser.add_argument("--agent-model", default=None, help="Modelo do agente (padrão: o do Claude Code, ou gpt-4o-mini).")
    parser.add_argument("--agent-timeout", type=int, default=900, help="Segundos por sessão do agente (padrão: 900).")
    parser.add_argument(
        "--verification-sources-strict",
        action="store_true",
        help="Motor verify: pula a hipótese sem arquivo em --verification-sources em vez de usar o recorte.",
    )
    parser.add_argument(
        "--spec-strategy",
        choices=["repair", "resample"],
        default="repair",
        help="Motor verify: 'repair' mostra o erro anterior à LLM; 'resample' faz amostras independentes "
             "com o mesmo orçamento (linha de base do reparo).",
    )
    parser.add_argument(
        "--no-capability-probes",
        dest="capability_probes",
        action="store_false",
        help="Motor verify: não roda as sondas de capacidade do ESBMC; todas as regras de reescrita "
             "ficam ligadas (para reproduzir uma rodada congelada).",
    )
    parser.add_argument(
        "--capability-cache",
        default="artifacts/esbmc_capabilities",
        metavar="DIR",
        help="Motor verify: cache das sondas, uma entrada por binário, flags e versão do ESBMC.",
    )
    parser.add_argument(
        "--heal",
        choices=list(HEAL_MODES),
        default="error+kb",
        help="Motor verify: self-healing quando o ESBMC não chega a veredito (ligado por padrão; 'none' desliga); "
             "'error' devolve a mensagem do ESBMC "
             "ao LLM, 'error+kb' também o README e os testes de regressão do checkout do ESBMC",
    )
    parser.add_argument("--heal-rounds", type=int, default=3, help="Rodadas de self-healing por hipótese")
    parser.add_argument("--heal-triage", action="store_true",
                        help="Não pede reparo para hipóteses que o ESBMC recusou como UNSUPPORTED (economiza chamadas; "
                             "pode perder confirmações que só apareceriam depois do reparo).")
    parser.add_argument("--claude-isolated", action="store_true",
                        help="Backend claude_cli: envia o prompt do pipeline como prompt de sistema, sem ferramentas, "
                             "skills nem servidores MCP, numa pasta vazia (CLAUDE.md do projeto não é lido; o global e hooks "
                             "podem ser). Muda a entrada do LLM: rodadas sem a flag não são "
                             "comparáveis. Ignorada pelos outros backends.")
    parser.add_argument("--operational-retries", type=int, default=0, metavar="N",
                        help="Falha operacional (timeout, resposta vazia): tenta de novo até N vezes com espera fixa "
                             "(2 s, 4 s, ...). 0 desliga. Cota esgotada nunca é retentada: a rodada para e retoma.")
    parser.add_argument("--operational-shrink-context", action="store_true",
                        help="Com --operational-retries: se o prompt estourar o contexto, corta o meio dele pela "
                             "metade e tenta de novo. Marca o caso como reduzido na telemetria.")
    parser.add_argument("--workers", type=int, default=1, metavar="N",
                        help="Hipóteses verificadas em paralelo (threads); 1 é o comportamento sequencial.")
    parser.add_argument(
        "--no-auto-lessons",
        dest="auto_lessons",
        action="store_false",
        help="Motor verify e agente do scan: desliga a coleta automática de candidatos de lição em quarentena.",
    )
    parser.add_argument(
        "--spec-context",
        choices=["none", "callers"],
        default="callers",
        help="Motor verify: 'callers' mostra ao LLM do spec as chamadas da função e os fatos de uso das entradas, "
             "e rejeita tipo contrariado pelo uso; 'none' é o pedido de antes (linha de base).",
    )
    parser.add_argument(
        "--verification-sources",
        default=None,
        metavar="DIR",
        help="Motor verify: verifica no arquivo de mesmo nome deste diretório (ex.: arquivo_com_bug) quando existir.",
    )
    parser.add_argument(
        "--fixed-sources",
        default=None,
        metavar="DIR",
        help="Motor verify: versões corrigidas (ex.: arquivo_corrigido) para o controle do oráculo de valor; "
             "o LLM nunca as vê.",
    )
    parser.add_argument(
        "--context-sources",
        default=None,
        metavar="DIR",
        help="Variante A11: lê o contexto (imports, classe, chamadores) do arquivo de mesmo nome deste "
             "diretório; padrão: --verification-sources.",
    )
    parser.add_argument(
        "--detection-cache", default=None, metavar="PASTA",
        help="Guarda a detecção de cada função por hash (código, modelo, prompt, variantes) e reutiliza nas próximas "
             "rodadas com a mesma configuração, sem nova chamada à LLM.",
    )
    parser.add_argument(
        "--v2-variants",
        default="",
        metavar="A1,A2",
        help="Variantes do prompt V2 (research_pipeline/llm/prompt_variants.py), aplicadas em ordem.",
    )
    parser.add_argument(
        "--example-pool",
        default=str(REPO_ROOT / "dataset/bugs_reais/ground_truths.json"),
        metavar="JSON",
        help="Variante A13: gabarito de onde saem os exemplos (funções em funcao_com_bug/ ao lado dele).",
    )
    parser.add_argument("--max-hypotheses-per-function", type=_positive_int, default=None, metavar="N",
                        help="Envia ao ESBMC só as N primeiras expressões distintas de cada função, na ordem "
                             "em que o LLM as escreveu (padrão: sem limite). As outras ficam no relatório.")
    parser.add_argument("--review-threshold", type=_review_score, default=None, metavar="NOTA",
                        help="Segundo passo de LLM: dá nota de 0 a 10 a cada hipótese e só envia à especificação "
                             "e ao ESBMC as de nota maior ou igual a NOTA (padrão: desligado). Erro do revisor "
                             "mantém a hipótese. As descartadas ficam no relatório (review_dropped).")
    parser.add_argument("--example-k", type=_positive_int, default=3, metavar="K",
                        help="Variante A13: quantos exemplos por função (padrão: 3).")
    parser.add_argument(
        "--v2-stage",
        choices=["end-to-end", "synthesis", "detection"],
        default="end-to-end",
        help=(
            "Modo V2: 'end-to-end' detecta e sintetiza; 'synthesis' usa "
            "hipóteses conhecidas somente para avaliar a geração de harness "
            "isoladamente (requer --ground-truth); 'detection' para depois da "
            "detecção, para comparar prompts sem gastar verificação."
        ),
    )
    parser.add_argument("--scan-repository-context", choices=("off", "evidence"), default="off",
                        help="Scan: contexto estático de integração e documentação, com origem (padrão: off).")
    parser.add_argument("--scan-limit", type=_positive_int, default=None, metavar="N",
                        help="Modo scan: analisa só as N primeiras funções do ranking (padrão: todas).")
    parser.add_argument("--scan-include-tests", action="store_true",
                        help="Modo scan: inclui arquivos e pastas de teste no grafo e na seleção.")
    parser.add_argument("--scan-include-examples", action="store_true",
                        help="Modo scan: inclui na seleção examples/, samples/, docs/ e setup.py (ficam fora por "
                             "padrão).")
    parser.add_argument("--scan-caller-depth", type=_positive_int, default=1, metavar="N",
                        help="Modo scan: níveis de chamadores no prompt de detecção; 2 mostra também quem chama os "
                             "chamadores (padrão: 1, só as chamadas diretas). Aumenta o prompt.")
    parser.add_argument("--scan-rank", choices=("callers", "pagerank"), default="callers",
                        help="Modo scan: ordena as funções pelo número de chamadores (padrão) ou pela centralidade "
                             "no grafo (PageRank).")
    parser.add_argument("--scan-only", action="append", default=[], metavar="FUNÇÃO",
                        help="Modo scan: analisa só esta função (nome qualificado, ex.: Classe.metodo, ou chave do "
                             "grafo); repita para várias. A seleção guarda a posição de cada uma no ranking completo.")
    parser.add_argument("--scan-focus", default="",
                        help="Modo scan: o que priorizar, em texto livre (ex.: \"só o parsing\"); entra no prompt de "
                             "detecção como preferência, sem mudar as regras.")
    parser.add_argument("--scan-verify", choices=("engine", "agent"), default="engine",
                        help="Modo scan: confirma as hipóteses pelo motor de regras (padrão) ou pelo agente do "
                             "harness (Claude Code com o plugin do ESBMC e o grafo consultável).")
    parser.add_argument("--scan-smells", action="store_true",
                        help="Modo scan: smells de arquitetura pelo grafo e candidatos a Feature Envy em "
                             "scan_smells.json; com --yes, o LLM julga cada candidato (exploratório, sem gabarito).")
    parser.add_argument("--yes", action="store_true",
                        help="Modo scan: confirma o gasto com a LLM; sem ele, só monta o grafo e a seleção.")
    return parser
