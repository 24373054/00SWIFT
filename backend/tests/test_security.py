"""Security primitive and audit-redaction tests."""

from core.security import hash_secret, redact_body, token_digest, verify_secret


def test_secret_hash_is_salted_and_verifiable():
    first = hash_secret("correct horse battery staple")
    second = hash_secret("correct horse battery staple")
    assert first != second
    assert verify_secret("correct horse battery staple", first)
    assert not verify_secret("wrong", first)


def test_token_digest_never_contains_raw_token():
    raw = "a-very-sensitive-bearer-token"
    digest = token_digest(raw)
    assert raw not in digest
    assert len(digest) == 64


def test_redact_json_and_form_bodies():
    json_body = redact_body(b'{"access_token":"secret","amount":10}', "application/json")
    form_body = redact_body(
        b"assertion=secret&scope=swift.api", "application/x-www-form-urlencoded"
    )
    assert "secret" not in json_body
    assert "secret" not in form_body
    assert "amount" in json_body
    assert "scope" in form_body
