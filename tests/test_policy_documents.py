from backend.ai_service.services.policy_documents import (
    PolicyChunker,
    PolicyDocument,
    PolicyDocumentIndexer,
)


class FakeIndices:
    def __init__(self) -> None:
        self.created = {}

    def exists(self, index):
        return index in self.created

    def create(self, index, mappings):
        self.created[index] = mappings


class FakeElasticsearch:
    def __init__(self) -> None:
        self.indices = FakeIndices()

    def ping(self):
        return True


class FakeEmbeddingClient:
    def embed(self, model: str, text: str):
        assert model == "nomic-embed-text"
        assert text
        return [0.1, 0.2, 0.3]


def test_policy_chunker_splits_document_with_overlap() -> None:
    document = PolicyDocument(
        document_id="remote-work-policy",
        title="Remote Work Policy",
        source_path="data/company_policies/remote-work-policy.pdf",
        text="abcdefghijklmnopqrstuvwxyz",
    )

    chunks = PolicyChunker(chunk_size=10, chunk_overlap=2).chunk(document)

    assert [chunk.text for chunk in chunks] == ["abcdefghij", "ijklmnopqr", "qrstuvwxyz"]
    assert chunks[0].chunk_id == "remote-work-policy:0"
    assert chunks[1].chunk_index == 1


def test_policy_indexer_creates_dense_vector_mapping() -> None:
    fake_es = FakeElasticsearch()
    indexer = PolicyDocumentIndexer(
        elasticsearch_client=fake_es,
        embedding_client=FakeEmbeddingClient(),
        index_name="company_policy_documents",
        embedding_model="nomic-embed-text",
        chunker=PolicyChunker(chunk_size=100, chunk_overlap=10),
    )

    indexer.ensure_index()

    mapping = fake_es.indices.created["company_policy_documents"]
    embedding_mapping = mapping["properties"]["embedding"]
    assert embedding_mapping["type"] == "dense_vector"
    assert embedding_mapping["dims"] == 3
    assert embedding_mapping["similarity"] == "cosine"
