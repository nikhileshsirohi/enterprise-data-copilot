from backend.ai_service.services.policy_documents import (
    PolicyChunker,
    PolicyDocument,
    PolicyDocumentError,
    PolicyDocumentIndexer,
    PolicyDocumentStorage,
    PolicyVectorSearcher,
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


class FakeSearchResponse:
    def __init__(self, body) -> None:
        self.body = body


class FakeDocumentListElasticsearch(FakeElasticsearch):
    def __init__(self) -> None:
        super().__init__()
        self.indices.created["company_policy_documents"] = {}

    def search(self, index, size, aggs):
        assert index == "company_policy_documents"
        assert size == 0
        assert aggs["documents"]["terms"]["field"] == "document_id"
        return FakeSearchResponse(
            {
                "aggregations": {
                    "documents": {
                        "buckets": [
                            {
                                "key": "travel-expense-policy",
                                "chunk_count": {"value": 3},
                                "max_chunk_index": {"value": 2.0},
                                "sample": {
                                    "hits": {
                                        "hits": [
                                            {
                                                "_source": {
                                                    "document_id": "travel-expense-policy",
                                                    "document_title": "Travel Expense Policy",
                                                    "source_path": (
                                                        "data/company_policies/"
                                                        "travel-expense-policy.pdf"
                                                    ),
                                                }
                                            }
                                        ]
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        )


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


def build_hit(chunk_id: str, title: str = "Travel Expense Policy"):
    return {
        "_score": 10.0,
        "_source": {
            "document_id": title.lower().replace(" ", "-"),
            "document_title": title,
            "source_path": f"data/company_policies/{title.lower().replace(' ', '-')}.pdf",
            "chunk_id": chunk_id,
            "chunk_index": 0,
            "text": "Meal reimbursement is capped at 60 USD per day.",
        },
    }


def test_policy_searcher_reciprocal_rank_fusion_merges_duplicate_chunks() -> None:
    searcher = PolicyVectorSearcher(
        elasticsearch_client=FakeElasticsearch(),
        embedding_client=FakeEmbeddingClient(),
        index_name="company_policy_documents",
        embedding_model="nomic-embed-text",
    )

    fused = searcher._reciprocal_rank_fusion(
        vector_hits=[build_hit("travel-expense-policy:0"), build_hit("remote-work-policy:0")],
        keyword_hits=[build_hit("travel-expense-policy:0"), build_hit("data-security-policy:0")],
    )

    assert [hit["_source"]["chunk_id"] for hit in fused] == [
        "travel-expense-policy:0",
        "remote-work-policy:0",
        "data-security-policy:0",
    ]
    assert fused[0]["_fusion_score"] > fused[1]["_fusion_score"]
    assert fused[0]["_score"] == 10.0


def test_policy_searcher_preserves_best_elasticsearch_score_after_fusion() -> None:
    searcher = PolicyVectorSearcher(
        elasticsearch_client=FakeElasticsearch(),
        embedding_client=FakeEmbeddingClient(),
        index_name="company_policy_documents",
        embedding_model="nomic-embed-text",
    )
    vector_hit = build_hit("travel-expense-policy:0")
    vector_hit["_score"] = 0.8375926
    keyword_hit = build_hit("travel-expense-policy:0")
    keyword_hit["_score"] = 0.0327868

    fused = searcher._reciprocal_rank_fusion(
        vector_hits=[vector_hit],
        keyword_hits=[keyword_hit],
    )

    assert fused[0]["_score"] == 0.8375926
    assert fused[0]["_fusion_score"] > 0


def test_policy_searcher_lists_indexed_documents_from_aggregations() -> None:
    searcher = PolicyVectorSearcher(
        elasticsearch_client=FakeDocumentListElasticsearch(),
        embedding_client=FakeEmbeddingClient(),
        index_name="company_policy_documents",
        embedding_model="nomic-embed-text",
    )

    documents = searcher.list_documents(limit=100)

    assert len(documents) == 1
    assert documents[0].document_id == "travel-expense-policy"
    assert documents[0].document_title == "Travel Expense Policy"
    assert documents[0].chunk_count == 3
    assert documents[0].max_chunk_index == 2


def test_policy_document_storage_saves_supported_base64_document(tmp_path) -> None:
    storage = PolicyDocumentStorage()

    stored = storage.save_base64_document(
        directory=str(tmp_path),
        filename="benefits-policy.txt",
        content_base64="QmVuZWZpdHMgcG9saWN5",
        max_bytes=100,
    )

    assert stored.filename == "benefits-policy.txt"
    assert stored.size_bytes == 15
    assert (tmp_path / "benefits-policy.txt").read_text() == "Benefits policy"


def test_policy_document_storage_rejects_path_segments(tmp_path) -> None:
    storage = PolicyDocumentStorage()

    try:
        storage.save_base64_document(
            directory=str(tmp_path),
            filename="../secrets.txt",
            content_base64="c2VjcmV0",
            max_bytes=100,
        )
    except PolicyDocumentError as exc:
        assert "path segments" in str(exc)
    else:
        raise AssertionError("Expected path segment validation to fail.")


def test_policy_document_storage_rejects_unsupported_extension(tmp_path) -> None:
    storage = PolicyDocumentStorage()

    try:
        storage.save_base64_document(
            directory=str(tmp_path),
            filename="policy.exe",
            content_base64="cG9saWN5",
            max_bytes=100,
        )
    except PolicyDocumentError as exc:
        assert "Unsupported policy document type" in str(exc)
    else:
        raise AssertionError("Expected extension validation to fail.")


def test_policy_document_storage_deletes_supported_document(tmp_path) -> None:
    storage = PolicyDocumentStorage()
    document_path = tmp_path / "benefits-policy.txt"
    document_path.write_text("Benefits policy")

    deleted = storage.delete_document(
        directory=str(tmp_path),
        filename="benefits-policy.txt",
    )

    assert deleted.filename == "benefits-policy.txt"
    assert deleted.deleted is True
    assert not document_path.exists()


def test_policy_document_storage_rejects_missing_delete_target(tmp_path) -> None:
    storage = PolicyDocumentStorage()

    try:
        storage.delete_document(
            directory=str(tmp_path),
            filename="missing-policy.txt",
        )
    except PolicyDocumentError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected missing policy delete validation to fail.")
