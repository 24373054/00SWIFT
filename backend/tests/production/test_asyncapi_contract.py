from pathlib import Path

import yaml


def test_asyncapi_lists_all_production_event_families():
    document = yaml.safe_load(Path("asyncapi/production-events.yaml").read_text(encoding="utf-8"))
    assert document["asyncapi"].startswith("3.")
    values = document["components"]["schemas"]["EventEnvelope"]["properties"]["event_type"]["enum"]
    families = {value.split(".", 1)[0] for value in values}
    assert families == {"payment", "funding", "fx", "message", "settlement", "compliance", "reconciliation", "case", "report"}
