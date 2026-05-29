---
name: rag-document-processing
description: Use when implementing document chunking, content hashing, Ollama /api/embed embeddings, embedding dimension validation, chunk metadata, chunk replacement, or RAG ingestion behavior.
---

# RAG Document Processing

Use this skill for chunking, embeddings, document hashing, and RAG ingestion behavior.

## Chunking

- Keep `ChunkingService` deterministic for the same `FileEntry`, chunk settings, and document id.
- Generate stable sequential `chunk_index` values starting at `0`.
- Preserve content hashes for each chunk.
- Include useful metadata such as source path and character offsets when available.
- Handle empty input explicitly. Return no chunks or raise a clear domain/application error according to the active contract; do not silently generate invalid chunks.
- Keep processing idempotency-friendly: unchanged file content should produce the same chunk sequence.

## Embeddings

- Use Ollama `/api/embed` through `httpx` for embedding generation.
- Keep request payloads aligned with Ollama's API: model plus ordered input texts.
- Preserve input order in output vectors.
- Validate vector count: number of returned vectors must match number of input texts.
- Validate vector order by preserving positional mapping from input chunks to returned embeddings.
- Validate vector dimensions as 768 unless the configured embedding model intentionally changes.
- Handle empty embedding input explicitly rather than sending ambiguous requests.
- Batch embedding requests consistently and concatenate results in input order.

## Replacement Semantics

- Recalculate chunks and embeddings when a document content hash changes.
- Replace all chunks for a modified document with the newly generated ordered chunk set.
- Do not append duplicate chunks for unchanged documents.
- Keep `knowledge_documents.content_hash`, `knowledge_chunks.chunk_index`, chunk metadata, and embeddings consistent in the same processing flow.

## Validation

- Add tests for chunk count, chunk overlap, chunk indexes, content hashes, metadata, empty input behavior, embedding batch order, vector count validation, and dimension validation when those behaviors change.
- Run `uv run pytest` and `uv run ruff check .` when Python code changes.
