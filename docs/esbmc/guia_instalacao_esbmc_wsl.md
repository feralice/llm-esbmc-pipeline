# Guia de instalação e primeiro uso do ESBMC-Python (WSL/Windows)

> Material de apoio pro estágio em docência. Roteiro testado para WSL2 com Ubuntu;
> notas ao final cobrem Linux nativo e macOS. Fonte oficial: `~/esbmc/website/content/docs/development/building.md`
> e `~/esbmc/website/content/docs/python/usage.md`, conferir se o repositório mudou antes de reusar em aula.

## 1. Por que WSL

O ESBMC não builda nativamente no Windows sem uma cadeia de ferramentas pesada
(Visual Studio, vcpkg, LLVM compilado na mão). Rodando dentro do WSL2, o build
segue exatamente o roteiro de Linux (Ubuntu/Debian), que é o caminho mais curto
e mais bem testado pelo próprio projeto.

## 2. Instalar o WSL2 com Ubuntu

No PowerShell como administrador:

```powershell
wsl --install -d Ubuntu
```

Reiniciar quando pedido. Na primeira abertura do Ubuntu, criar usuário e senha
Linux (independentes da conta Windows).

## 3. Pré-requisitos de build (dentro do WSL/Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build git bison flex python3 libboost-all-dev g++-multilib
```

LLVM/Clang, Z3 e as bibliotecas fmt/nlohmann-json/yaml-cpp/immer são baixadas
automaticamente pela flag `-DDOWNLOAD_DEPENDENCIES=1` no passo de configuração,
não precisam ser instaladas manualmente.

## 4. Obter o código e compilar com o frontend Python habilitado

```bash
git clone https://github.com/esbmc/esbmc.git
cd esbmc
cmake -GNinja -Bbuild -DDOWNLOAD_DEPENDENCIES=1 -DENABLE_Z3=1 -DENABLE_PYTHON_FRONTEND=On
ninja -C build
```

O binário fica em `build/src/esbmc/esbmc`. `ast2json` já vem embutido no
código-fonte, não precisa de `pip install` separado. Adicionar ao PATH
(ajustar `~/.bashrc`):

```bash
export PATH="$HOME/esbmc/build/src/esbmc:$PATH"
```

Verificar:

```bash
esbmc --version
```

## 5. Um exemplo, do início ao fim

`docs/exemplos_esbmc/01_divisao_por_zero.py` (nesta pasta):

```python
import random as rand

def div1(cond: int, x: int) -> int:
    if not cond:
        return 42 // x
    else:
        return x // 10

cond: int = rand.random()
x: int = rand.random()

assert div1(cond, x) != 1
```

Roda sem erro no interpretador Python normal. Rodando com ESBMC:

```bash
esbmc docs/exemplos_esbmc/01_divisao_por_zero.py
```

Saída real (ESBMC 8.4.0, testada nesta máquina):

```
Violated property:
  file 01_divisao_por_zero.py line 19 column 8 function div1
  division by zero
  CWE: CWE-369
  x != 0

VERIFICATION FAILED
```

O ESBMC prova que existe um caminho (`cond` e `x` viram 0 depois do cast)
onde `42 // x` quebra, e devolve a restrição concreta (`x != 0`) que falha.
Esse contraexemplo é o ponto de partida do tópico "Leitura e interpretação
de contraexemplos" do roteiro.

## 6. Comandos essenciais

```bash
esbmc arquivo.py                      # verificacao basica, unwind padrao = 1
esbmc arquivo.py --unwind 10          # aumenta o limite de desdobramento de laco
esbmc arquivo.py --incremental-bmc    # aumenta o limite aos poucos ate achar bug ou esgotar
esbmc arquivo.py --multi-property     # continua apos a 1a violacao, reporta todas
esbmc arquivo.py --function nome_da_funcao   # verifica so uma funcao, nao o arquivo inteiro
esbmc arquivo.py --python /caminho/python3   # escolhe o interpretador usado internamente
```

Harness na mão (entrada simbólica em vez de `random`):

```python
def divide(a: int, b: int) -> int:
    return a // b

b: int = __VERIFIER_nondet_int()
__ESBMC_assume(b > 0)          # restringe o dominio: so valores positivos
assert divide(10, b) >= 0
```

Cuidado didático: `b != 0` sozinho não bastaria aqui, porque `10 // b` com
`b` negativo dá resultado negativo em Python (divisão inteira arredonda pra
baixo) e o `assert >= 0` falharia mesmo sem divisão por zero. É um bom
exemplo pra turma de guarda incompleta: a pré-condição precisa cobrir
exatamente o que a propriedade exige, não só "não é zero".

## 7. O que o ESBMC-Python prova (e o que não prova)

Propriedades verificadas: divisão por zero, acesso fora dos limites de
índice, overflow aritmético e `assert` definido pelo usuário. Fora dessas
quatro famílias, "VERIFICATION SUCCESSFUL" não significa corretude
funcional geral, só que a propriedade escrita não foi violada dentro do
limite analisado.

## 8. Outras plataformas

**Linux nativo:** mesmos comandos do passo 3-4, sem WSL.

**macOS:**

```bash
brew install llvm@21 z3 boost cmake ninja python bison
cmake -GNinja -Bbuild -DDOWNLOAD_DEPENDENCIES=1 -DENABLE_Z3=1 -DENABLE_PYTHON_FRONTEND=On \
  -DLLVM_DIR=$(brew --prefix llvm@21)/lib/cmake/llvm \
  -DClang_DIR=$(brew --prefix llvm@21)/lib/cmake/clang \
  -DZ3_DIR=$(brew --prefix z3)
ninja -C build
```

**Windows nativo (sem WSL):** possível, mas pesado (Visual Studio + vcpkg +
LLVM compilado manualmente). Não recomendado pra disciplina.

## Requisitos mínimos

Pelo menos 6 GB de RAM para o build. Python 3.10 ou mais recente para o
frontend Python.
