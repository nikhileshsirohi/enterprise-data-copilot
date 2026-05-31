from functools import lru_cache
from typing import Any

from elasticsearch import Elasticsearch

from backend.ai_service.schemas.metadata import MetadataSearchResult
from backend.django_app.core.metadata import SCHEMA_METADATA_INDEX
from backend.shared.config import get_settings


class MetadataRetriever:
    def __init__(self, client: Elasticsearch, index_name: str = SCHEMA_METADATA_INDEX) -> None:
        self.client = client
        self.index_name = index_name

    def search(self, query: str, limit: int = 5) -> list[MetadataSearchResult]:
        if not self.client.ping():
            raise ConnectionError("Elasticsearch is not reachable")

        response = self.client.search(
            index=self.index_name,
            size=limit,
            query={
                "multi_match": {
                    "query": query,
                    "fields": [
                        "business_name^3",
                        "description^2",
                        "examples^2",
                        "table",
                        "column",
                    ],
                    "type": "best_fields",
                }
            },
        )
        return [self._to_result(hit) for hit in response.body["hits"]["hits"]]

    def _to_result(self, hit: dict[str, Any]) -> MetadataSearchResult:
        source = hit["_source"]
        return MetadataSearchResult(
            table=source["table"],
            column=source["column"],
            business_name=source["business_name"],
            description=source["description"],
            data_type=source["data_type"],
            examples=source.get("examples", []),
            score=float(hit["_score"]),
        )


@lru_cache
def get_metadata_retriever() -> MetadataRetriever:
    settings = get_settings()
    return MetadataRetriever(client=Elasticsearch(settings.elasticsearch_url))
