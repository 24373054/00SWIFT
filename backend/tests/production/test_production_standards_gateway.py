from production.standards import validate_payload


def test_production_standards_gateway_rejects_missing_message_sections():
    findings = validate_payload("pacs.008", {"header": {}, "document": {}})
    assert findings and all(item["severity"] == "ERROR" for item in findings)


def test_production_standards_gateway_accepts_canonical_payment_shape():
    findings = validate_payload("pacs.008", {"header": {"biz_msg_id": "i1"}, "document": {"message_id": "i1", "uetr": "u", "amount": "1.00", "currency": "CNY"}})
    assert findings == []
