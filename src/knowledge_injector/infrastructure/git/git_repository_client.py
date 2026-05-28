"""Stub Git repository client — Phase 2 placeholder."""

from knowledge_injector.domain.models import FileEntry
from knowledge_injector.domain.ports import RepositoryClientPort
from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class GitRepositoryClient(RepositoryClientPort):
    """Clones or updates a Git repository and lists eligible files.

    This is a Phase 1 stub. Full implementation in Phase 2.
    """

    def __init__(
        self,
        repo_url: str,
        branch: str,
        workdir: str,
        auth_mode: str = "none",
    ) -> None:
        self.repo_url = repo_url
        self.branch = branch
        self.workdir = workdir
        self.auth_mode = auth_mode

    def sync(self) -> str:
        # TODO Phase 2: implement clone / pull and return HEAD sha
        raise NotImplementedError(
            "GitRepositoryClient.sync() will be implemented in Phase 2"
        )

    def list_files(
        self,
        base_path: str,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> list[FileEntry]:
        # TODO Phase 2: implement file discovery with fnmatch patterns
        raise NotImplementedError(
            "GitRepositoryClient.list_files() will be implemented in Phase 2"
        )
