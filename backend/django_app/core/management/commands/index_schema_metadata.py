from django.core.management.base import BaseCommand
from elasticsearch import Elasticsearch, helpers

from backend.django_app.core.metadata import SCHEMA_METADATA, SCHEMA_METADATA_INDEX
from backend.shared.config import get_settings


class Command(BaseCommand):
    help = "Index business schema metadata into Elasticsearch."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate the metadata index before indexing.",
        )

    def handle(self, *args, **options):
        settings = get_settings()
        client = Elasticsearch(settings.elasticsearch_url)

        if not client.ping():
            raise RuntimeError(f"Elasticsearch is not reachable at {settings.elasticsearch_url}")

        if options["reset"] and client.indices.exists(index=SCHEMA_METADATA_INDEX):
            client.indices.delete(index=SCHEMA_METADATA_INDEX)

        if not client.indices.exists(index=SCHEMA_METADATA_INDEX):
            client.indices.create(
                index=SCHEMA_METADATA_INDEX,
                mappings={
                    "properties": {
                        "table": {"type": "keyword"},
                        "column": {"type": "keyword"},
                        "business_name": {"type": "text"},
                        "description": {"type": "text"},
                        "data_type": {"type": "keyword"},
                        "examples": {"type": "text"},
                    }
                },
            )

        actions = [
            {
                "_index": SCHEMA_METADATA_INDEX,
                "_id": f"{item['table']}.{item['column']}",
                "_source": item,
            }
            for item in SCHEMA_METADATA
        ]
        success_count, _errors = helpers.bulk(client, actions, refresh=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {success_count} schema metadata documents into {SCHEMA_METADATA_INDEX}."
            )
        )
