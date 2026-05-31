from backend.django_app.core.metadata import SCHEMA_METADATA, SCHEMA_METADATA_INDEX


def test_schema_metadata_has_required_fields() -> None:
    required_fields = {"table", "column", "business_name", "description", "data_type", "examples"}

    assert SCHEMA_METADATA_INDEX == "business_schema_metadata"
    assert len(SCHEMA_METADATA) >= 15
    assert all(required_fields.issubset(item.keys()) for item in SCHEMA_METADATA)


def test_schema_metadata_contains_core_business_terms() -> None:
    business_names = {item["business_name"] for item in SCHEMA_METADATA}

    assert "Committed Quantity" in business_names
    assert "Supplier" in business_names
    assert "Available Stock" in business_names
    assert "Sales Order Quantity" in business_names
