"""Domain models representing core business entities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class IngestionStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    IGNORED = "ignored"


class SourceType(str, Enum):
    GIT = "git"


@dataclass
class KnowledgeSource:
    name: str
    source_type: SourceType
    repo_url: str
    branch: str
    base_path: str
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class IngestionRun:
    source_id: UUID
    status: IngestionStatus
    started_at: datetime
    id: UUID = field(default_factory=uuid4)
    finished_at: Optional[datetime] = None
    repo_commit_sha: Optional[str] = None
    files_seen: int = 0
    files_changed: int = 0
    files_deleted: int = 0
    chunks_created: int = 0
    chunks_updated: int = 0
    chunks_deleted: int = 0
    error_message: Optional[str] = None
    next_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class KnowledgeDocument:
    source_id: UUID
    path: str
    content_hash: str
    status: DocumentStatus
    id: UUID = field(default_factory=uuid4)
    last_commit_sha: Optional[str] = None
    title: Optional[str] = None
    mime_type: str = "text/plain"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class KnowledgeChunk:
    document_id: UUID
    chunk_index: int
    content: str
    content_hash: str
    id: UUID = field(default_factory=uuid4)
    token_count: Optional[int] = None
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class FileEntry:
    """Represents a file discovered in a knowledge source."""

    path: str
    content: str
    content_hash: str
    relative_path: str
