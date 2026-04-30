# Prompt — Passo 3: GitRepositoryClient (clone/pull + listagem de arquivos)

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para executar **somente o Passo 3** do plano de implementação. Cole tudo da seção "PROMPT" abaixo.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: [docs/implementation-plan.md](../../implementation-plan.md). Esta tarefa cobre **apenas o Passo 3** da Seção 4.
- Já está pronto: schema `knowledge`, ORM, domain models, ports, CLI, config, `Database` (Passo 1) e `Repositories` (Passo 2).
- Objetivo deste passo: implementar o `GitRepositoryClient` que hoje é um stub com `NotImplementedError` em ambos os métodos (`sync` e `list_files`).

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas** o Passo 3 do plano de implementação MVP.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `docs/implementation-plan.md` — Seção 4, Passo 3 (GitRepositoryClient) e Seção 3 (onde o cliente entra no fluxo do `IngestionService`).
2. `src/knowledge_injector/domain/models.py` — em particular o dataclass `FileEntry` (campos `path`, `content`, `content_hash`, `relative_path`).
3. `src/knowledge_injector/domain/ports.py` — `RepositoryClientPort` (assinaturas que você deve implementar; **não modificar**).
4. `src/knowledge_injector/infrastructure/git/git_repository_client.py` — stub atual que você vai substituir. Note o construtor já existente: `(repo_url, branch, workdir, auth_mode='none')`. **Não altere o construtor.**
5. `src/knowledge_injector/config.py` — `IngestionSettings.workdir`, `include_patterns`, `exclude_patterns`; `KnowledgeSourceSettings.repo_url`, `repo_branch`, `repo_base_path`, `repo_auth_mode`.
6. `pyproject.toml` — confirme que `gitpython>=3.1` já está disponível (você vai usar `git.Repo`).

## Tarefa

Substituir o stub em `src/knowledge_injector/infrastructure/git/git_repository_client.py` por uma implementação real. O construtor permanece como está; implemente os dois métodos do port.

### A) `sync(self) -> str`

Garante que `self.workdir` contém uma cópia atualizada do `repo_url` na branch `self.branch`, e retorna o SHA do `HEAD` atual (40 caracteres hex).

Comportamento:

- Se `self.workdir` não existe ou não é um repositório git válido (ex.: diretório vazio, ou existe mas sem `.git/`):
  - Criar o diretório pai se necessário.
  - `git.Repo.clone_from(self.repo_url, self.workdir, branch=self.branch)`.
  - Logar `git.clone` com `repo_url` e `branch`.
- Se já é um repositório git válido:
  - Abrir com `git.Repo(self.workdir)`.
  - `repo.remotes.origin.fetch()`.
  - `repo.git.checkout(self.branch)`.
  - `repo.git.reset("--hard", f"origin/{self.branch}")` — garante alinhamento exato com o remoto, descarta qualquer estado local.
  - Logar `git.fetch` com `branch`.
- Retornar `repo.head.commit.hexsha`.

Detecção de "repo válido": tente `git.Repo(self.workdir)` e capture `git.exc.InvalidGitRepositoryError` e `git.exc.NoSuchPathError` para decidir clone vs. pull. Não invente heurísticas baseadas em `os.path` se a biblioteca já oferece a verificação correta.

**Auth guard:** se `self.auth_mode != "none"`, levante `NotImplementedError("auth_mode={mode} not supported in MVP")` **logo no início do `sync()`**, antes de qualquer operação git. O MVP só suporta repositórios públicos ou `file://`.

### B) `list_files(self, base_path, include_patterns, exclude_patterns) -> list[FileEntry]`

Caminha pelo diretório `self.workdir / base_path` e devolve `FileEntry` para cada arquivo que casa com `include_patterns` e **não** casa com nenhum `exclude_patterns`.

Comportamento:

- Resolver o diretório raiz da varredura: `root = Path(self.workdir) / base_path` (se `base_path` for `""`, vira `Path(self.workdir)`).
- Se `root` não existe, levantar `FileNotFoundError` com mensagem clara (não retornar lista vazia silenciosamente — isso é um erro de configuração).
- **Sempre** ignorar qualquer caminho que contenha um diretório `.git` em qualquer nível, mesmo que `exclude_patterns` não cubra. (Garantia defensiva; o git interno não deve ser enviado como conteúdo.)
- Para cada arquivo encontrado dentro de `root`:
  1. Calcular `relative_path` como string POSIX relativa a `root` (use `Path.relative_to(root).as_posix()` — sempre `/` como separador, nunca `\`, mesmo no Windows).
  2. Aplicar `include_patterns`: o arquivo só passa se **algum** padrão casar.
  3. Aplicar `exclude_patterns`: se **algum** padrão casar, descartar.
  4. Pular arquivos > 5 MB (`Path.stat().st_size > 5 * 1024 * 1024`). Logar `git.list_files.skipped_large` com `path` e `size_bytes`.
  5. Ler bytes do arquivo, decodificar com `decode("utf-8", errors="replace")`.
  6. Calcular `content_hash = hashlib.sha256(<bytes brutos>).hexdigest()` — use os **bytes lidos do disco**, não a string decodificada (hash precisa ser estável e independente do `errors="replace"`).
  7. `path` do `FileEntry` é o caminho absoluto em string (`str(arquivo.resolve())`); `relative_path` é o relativo POSIX calculado em (1).
- Retornar a lista ordenada por `relative_path` (determinismo facilita debugging e testes).

**Semântica dos patterns:** use `pathlib.PurePosixPath(relative_path).match(pattern)` e garanta que `**` funciona corretamente (ex.: `**/*.md` deve casar `a.md` e `sub/b.md`). Se `Path.match` da sua versão não suportar `**` recursivo de forma confiável, use `Path(root).glob(pattern)` para construir o conjunto de inclusões e `Path(root).glob(pattern)` para o conjunto de exclusões — `Path.glob` suporta `**` nativamente em todas as versões 3.10+. Escolha **uma** abordagem e seja consistente.

### Constraints

- **Síncrono.** Sem `async`/`asyncio`.
- **Sem novas dependências.** `gitpython` já está em `pyproject.toml`.
- **Não modifique outros arquivos** além de `git_repository_client.py`. Em particular: não altere `ports.py`, `models.py`, `containers.py` nem o `.env`.
- **Não toque no construtor.** Os 4 parâmetros (`repo_url`, `branch`, `workdir`, `auth_mode`) e seus atributos `self.*` devem permanecer iguais.
- **Logging via structlog.** `from knowledge_injector.infrastructure.logging.logger import get_logger` (já importado no stub).
- **Type hints completos.** Python 3.12 — use `|` em vez de `Optional`.
- **Sem comentários decorativos.** Apenas onde a lógica não for óbvia (ex.: por que o hash é dos bytes brutos, por que `**/.git/**` é filtro defensivo).
- **Não comece o Passo 4** (`ChunkingService`). Pare assim que o Passo 3 estiver verificável.

## Validação (você executa antes de declarar concluído)

A validação cria um repositório git local hermético em `/tmp` para evitar dependência de rede ou do estado do `homelab-infra`. Execute a partir da raiz do projeto:

```bash
uv run python -c "
import subprocess, tempfile, hashlib
from pathlib import Path
from knowledge_injector.infrastructure.git.git_repository_client import GitRepositoryClient

# 1. Cria um repo-fonte hermético com arquivos conhecidos
with tempfile.TemporaryDirectory() as src_dir:
    src = Path(src_dir)
    subprocess.run(['git', 'init', '-q', '-b', 'main', src_dir], check=True)
    subprocess.run(['git', '-C', src_dir, 'config', 'user.email', 'test@test'], check=True)
    subprocess.run(['git', '-C', src_dir, 'config', 'user.name', 'test'], check=True)
    (src / 'docs').mkdir()
    (src / 'docs' / 'a.md').write_text('# A')
    (src / 'docs' / 'b.txt').write_text('hello')
    (src / 'docs' / 'sub').mkdir()
    (src / 'docs' / 'sub' / 'c.md').write_text('# C')
    (src / 'README.md').write_text('# Top')
    subprocess.run(['git', '-C', src_dir, 'add', '.'], check=True)
    subprocess.run(['git', '-C', src_dir, 'commit', '-q', '-m', 'init'], check=True)

    # 2. Primeira sync = clone
    with tempfile.TemporaryDirectory() as work_dir:
        # workdir precisa não existir para forçar clone; remova o tempdir vazio
        Path(work_dir).rmdir()

        client = GitRepositoryClient(
            repo_url=f'file://{src_dir}',
            branch='main',
            workdir=work_dir,
            auth_mode='none',
        )
        sha1 = client.sync()
        assert isinstance(sha1, str) and len(sha1) == 40, f'expected 40-char SHA, got {sha1!r}'
        assert (Path(work_dir) / '.git').is_dir(), 'clone did not create .git'

        # 3. Segunda sync = fetch + reset (idempotente, mesmo SHA)
        sha2 = client.sync()
        assert sha1 == sha2, f'sha mismatch on re-sync: {sha1} vs {sha2}'

        # 4. list_files com include único (**/*.md) sob docs/
        files = client.list_files(
            base_path='docs',
            include_patterns=['**/*.md'],
            exclude_patterns=[],
        )
        rels = sorted(f.relative_path for f in files)
        assert rels == ['a.md', 'sub/c.md'], f'unexpected rels: {rels}'

        # FileEntry shape
        a_md = next(f for f in files if f.relative_path == 'a.md')
        assert a_md.content == '# A'
        expected_hash = hashlib.sha256(b'# A').hexdigest()
        assert a_md.content_hash == expected_hash, 'hash deve ser sha256 dos bytes brutos'
        assert Path(a_md.path).is_absolute(), 'path deve ser absoluto'

        # 5. include + exclude combinados
        files2 = client.list_files(
            base_path='docs',
            include_patterns=['**/*.md', '**/*.txt'],
            exclude_patterns=['sub/**'],
        )
        rels2 = sorted(f.relative_path for f in files2)
        assert rels2 == ['a.md', 'b.txt'], f'exclude failed: {rels2}'

        # 6. base_path inexistente => FileNotFoundError
        try:
            client.list_files('nope', ['**/*'], [])
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('expected FileNotFoundError for missing base_path')

# 7. auth_mode != 'none' => NotImplementedError
try:
    GitRepositoryClient(
        repo_url='file:///tmp/x', branch='main', workdir='/tmp/x', auth_mode='token',
    ).sync()
except NotImplementedError:
    pass
else:
    raise AssertionError('expected NotImplementedError for auth_mode=token')

print('OK — GitRepositoryClient: clone + fetch idempotente + list_files (include/exclude/erros) + auth guard')
"
```

Se qualquer asserção falhar, corrija e re-rode antes de finalizar.

### Validação opcional contra o `homelab-infra` real (não obrigatória)

Se quiser confirmar contra um repo real, aponte para a cópia local (sem rede):

```bash
uv run python -c "
import tempfile
from pathlib import Path
from knowledge_injector.infrastructure.git.git_repository_client import GitRepositoryClient

with tempfile.TemporaryDirectory() as work_dir:
    Path(work_dir).rmdir()
    client = GitRepositoryClient(
        repo_url='file:///home/brunohsouza/code/Personal/homelab-infra',
        branch='main',
        workdir=work_dir,
        auth_mode='none',
    )
    sha = client.sync()
    files = client.list_files('docs', ['**/*.md'], ['.git/**'])
    print(f'sha={sha[:7]} files={len(files)}')
"
```

Esperado: imprime um SHA curto e uma contagem `> 0`. Se o repo local não existir ou a branch `main` não estiver lá, **não tente corrigir** — pule esta validação opcional.

## Pré-condições do ambiente (já validadas)

- Binário `git` disponível no `PATH` (necessário para `gitpython` operar).
- `gitpython>=3.1` instalado via `uv sync` (já em `pyproject.toml`).
- `/tmp` gravável (usado pela validação para repos efêmeros).

Se algum desses pré-requisitos falhar, **pare e reporte ao usuário** — não tente instalar git nem mexer em `pyproject.toml`.

## Entregável final

- Um único arquivo modificado: `src/knowledge_injector/infrastructure/git/git_repository_client.py`.
- A validação principal passando (`OK — GitRepositoryClient: ...`).
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado e qual validação rodou.

Não escreva README, não atualize `implementation-plan.md`, não crie testes em `tests/` (isso fica para outra fase), não avance para o Passo 4.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- A maior pegadinha desse passo é o suporte a `**` em globs. Em Python 3.12, `Path.match("**/*.md")` **não** casa recursivamente da forma que muita gente espera; `Path.glob("**/*.md")` casa. Se o agente reclamar de comportamento inconsistente, oriente a usar `Path.glob` para construir os conjuntos de inclusão/exclusão em vez de iterar arquivo a arquivo com `match`.
- O `reset --hard` no `sync()` é deliberado: garante que mudanças locais acidentais no `workdir` nunca quebram a próxima sincronização. Se o agente sugerir `pull` em vez de `fetch + reset`, recuse — `pull` pode falhar com merge conflicts em estados inesperados.
- O hash deve vir dos **bytes brutos** lidos do disco, não da string decodificada. `decode(errors="replace")` introduz `�` em arquivos não-utf8, o que mudaria o hash a cada execução em alguns casos extremos.
- A validação principal cria um repo em `/tmp` com `git init -b main`. Isso requer git ≥ 2.28 (lançado em 2020). WSL atual deve estar coberto. Se falhar, o sintoma é `unknown switch '-b'`.
- Próximo prompt nesta série será `passo-04-chunking-service.md` — só crie depois que este passo estiver validado.
- Se o agente tentar mapear autenticação via `GIT_ASKPASS` ou tokens "para já deixar pronto", interrompa: o MVP é explícito sobre `auth_mode != "none"` levantar `NotImplementedError`. Reduzir escopo é mais importante que prever o futuro aqui.
