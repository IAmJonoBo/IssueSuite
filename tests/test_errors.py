from __future__ import annotations

from issuesuite.errors import classify_error, redact


def test_classify_rate_limit():
    info = classify_error(RuntimeError('API Rate Limit Exceeded'))
    assert info.category == 'github.rate_limit'
    assert info.transient is True


def test_classify_abuse():
    info = classify_error(RuntimeError('Abuse detection triggered'))
    assert info.category == 'github.abuse'
    assert info.transient is True


def test_classify_network():
    info = classify_error(RuntimeError('Connection reset by peer'))
    assert info.category == 'network'
    assert info.transient is True


def test_classify_parse():
    info = classify_error(RuntimeError('YAML ScannerError near line 3'))
    assert info.category == 'parse'
    assert info.transient is False


def test_classify_generic():
    info = classify_error(ValueError('Some other problem'))
    assert info.category == 'generic'


def test_redact_tokens():
    key_header = "-----BEGIN " "PRIVATE KEY-----"
    key_footer = "-----END " "PRIVATE KEY-----"
    sample = (
        "Token ghp_ABCDEFGHIJKLMNOPQRSTUVWX plus github_pat_1234567890abcdefghijkl "
        f"and key block\n{key_header}\nABCDEF\n{key_footer}"
    )
    out = redact(sample)
    assert 'ghp_' not in out
    assert 'github_pat_' not in out
    # Entire key block should be redacted
    assert '<redacted>' in out
