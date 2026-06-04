from django.core.management.base import BaseCommand

from backend.ai_service.services.policy_documents import (
    PolicyDocumentLoader,
    build_policy_indexer,
)
from backend.shared.config import get_settings


class Command(BaseCommand):
    help = "Index company policy documents into Elasticsearch for RAG."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate the policy vector index before indexing.",
        )

    def handle(self, *args, **options):
        settings = get_settings()
        documents = PolicyDocumentLoader().load_directory(settings.policy_documents_dir)
        if not documents:
            self.stdout.write(
                self.style.WARNING(
                    f"No policy documents found in {settings.policy_documents_dir}."
                )
            )
            return

        indexer = build_policy_indexer()
        if options["reset"]:
            indexer.recreate_index()

        chunk_count = indexer.index_documents(documents)
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {chunk_count} policy chunks from {len(documents)} documents "
                f"into {settings.policy_documents_index}."
            )
        )
