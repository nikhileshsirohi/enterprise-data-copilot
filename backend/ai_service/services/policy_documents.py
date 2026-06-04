import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch, helpers

from backend.ai_service.schemas.policies import PolicySearchResult
from backend.ai_service.services.ollama_client import OllamaClient
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class PolicyDocumentError(RuntimeError):
    pass


@dataclass(frozen=True)
class PolicyDocument:
    document_id: str
    title: str
    source_path: str
    text: str


@dataclass(frozen=True)
class PolicyChunk:
    document_id: str
    document_title: str
    source_path: str
    chunk_id: str
    chunk_index: int
    text: str


class PolicyDocumentLoader:
    supported_suffixes = {".pdf", ".txt", ".md"}

    def load_directory(self, directory: str) -> list[PolicyDocument]:
        base_path = Path(directory)
        if not base_path.exists():
            raise PolicyDocumentError(f"Policy document directory does not exist: {directory}")

        documents = []
        for path in sorted(base_path.iterdir()):
            if not path.is_file() or path.suffix.lower() not in self.supported_suffixes:
                continue
            text = self._extract_text(path).strip()
            if not text:
                logger.warning("policy_document.empty path=%s", path)
                continue
            documents.append(
                PolicyDocument(
                    document_id=path.stem,
                    title=path.stem.replace("-", " ").replace("_", " ").title(),
                    source_path=str(path),
                    text=text,
                )
            )
        return documents

    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(path)
        return path.read_text(encoding="utf-8")

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise PolicyDocumentError(
                "pypdf is required to ingest PDF policy documents. "
                "Run: pip install -r requirements/dev.txt"
            ) from exc

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)


class PolicyChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("policy_chunk_overlap must be smaller than policy_chunk_size.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: PolicyDocument) -> list[PolicyChunk]:
        text = " ".join(document.text.split())
        chunks = []
        start = 0
        chunk_index = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    PolicyChunk(
                        document_id=document.document_id,
                        document_title=document.title,
                        source_path=document.source_path,
                        chunk_id=f"{document.document_id}:{chunk_index}",
                        chunk_index=chunk_index,
                        text=chunk_text,
                    )
                )
                chunk_index += 1
            if end >= len(text):
                break
            start = max(end - self.chunk_overlap, 0)
        return chunks


class PolicyDocumentIndexer:
    def __init__(
        self,
        *,
        elasticsearch_client: Elasticsearch,
        embedding_client: OllamaClient,
        index_name: str,
        embedding_model: str,
        chunker: PolicyChunker,
    ) -> None:
        self.elasticsearch_client = elasticsearch_client
        self.embedding_client = embedding_client
        self.index_name = index_name
        self.embedding_model = embedding_model
        self.chunker = chunker

    def recreate_index(self) -> None:
        if self.elasticsearch_client.indices.exists(index=self.index_name):
            self.elasticsearch_client.indices.delete(index=self.index_name)
        self.ensure_index()

    def ensure_index(self) -> None:
        if self.elasticsearch_client.indices.exists(index=self.index_name):
            return

        sample_embedding = self.embedding_client.embed(
            model=self.embedding_model,
            text="policy document embedding dimension probe",
        )
        self.elasticsearch_client.indices.create(
            index=self.index_name,
            mappings={
                "properties": {
                    "document_id": {"type": "keyword"},
                    "document_title": {"type": "text"},
                    "source_path": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": len(sample_embedding),
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

    def index_documents(self, documents: list[PolicyDocument]) -> int:
        if not self.elasticsearch_client.ping():
            raise ConnectionError("Elasticsearch is not reachable")

        self.ensure_index()
        chunks = [chunk for document in documents for chunk in self.chunker.chunk(document)]
        actions = []
        for chunk in chunks:
            embedding = self.embedding_client.embed(model=self.embedding_model, text=chunk.text)
            actions.append(
                {
                    "_index": self.index_name,
                    "_id": chunk.chunk_id,
                    "_source": {
                        "document_id": chunk.document_id,
                        "document_title": chunk.document_title,
                        "source_path": chunk.source_path,
                        "chunk_id": chunk.chunk_id,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "embedding": embedding,
                    },
                }
            )

        if not actions:
            return 0

        success_count, _errors = helpers.bulk(
            self.elasticsearch_client,
            actions,
            refresh=True,
        )
        logger.info("policy_documents.indexed index=%s chunks=%s", self.index_name, success_count)
        return int(success_count)


class PolicyVectorSearcher:
    def __init__(
        self,
        *,
        elasticsearch_client: Elasticsearch,
        embedding_client: OllamaClient,
        index_name: str,
        embedding_model: str,
    ) -> None:
        self.elasticsearch_client = elasticsearch_client
        self.embedding_client = embedding_client
        self.index_name = index_name
        self.embedding_model = embedding_model

    def search(self, query: str, limit: int = 5) -> list[PolicySearchResult]:
        if not self.elasticsearch_client.ping():
            raise ConnectionError("Elasticsearch is not reachable")

        query_embedding = self.embedding_client.embed(model=self.embedding_model, text=query)
        response = self.elasticsearch_client.search(
            index=self.index_name,
            knn={
                "field": "embedding",
                "query_vector": query_embedding,
                "k": limit,
                "num_candidates": max(limit * 10, 50),
            },
            size=limit,
        )
        return [self._to_result(hit) for hit in response.body["hits"]["hits"]]

    def _to_result(self, hit: dict[str, Any]) -> PolicySearchResult:
        source = hit["_source"]
        return PolicySearchResult(
            document_id=source["document_id"],
            document_title=source["document_title"],
            source_path=source["source_path"],
            chunk_id=source["chunk_id"],
            chunk_index=int(source["chunk_index"]),
            text=source["text"],
            score=float(hit["_score"]),
        )


def build_policy_indexer() -> PolicyDocumentIndexer:
    settings = get_settings()
    return PolicyDocumentIndexer(
        elasticsearch_client=Elasticsearch(settings.elasticsearch_url),
        embedding_client=OllamaClient(settings.ollama_base_url),
        index_name=settings.policy_documents_index,
        embedding_model=settings.ollama_embedding_model,
        chunker=PolicyChunker(
            chunk_size=settings.policy_chunk_size,
            chunk_overlap=settings.policy_chunk_overlap,
        ),
    )


def build_policy_searcher() -> PolicyVectorSearcher:
    settings = get_settings()
    return PolicyVectorSearcher(
        elasticsearch_client=Elasticsearch(settings.elasticsearch_url),
        embedding_client=OllamaClient(settings.ollama_base_url),
        index_name=settings.policy_documents_index,
        embedding_model=settings.ollama_embedding_model,
    )
