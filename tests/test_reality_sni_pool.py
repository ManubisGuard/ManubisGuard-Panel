from app.models.settings import DEFAULT_REALITY_SNI_POOL, General


def test_reality_sni_pool_has_default_candidates():
    settings = General()
    assert settings.reality_sni_pool == DEFAULT_REALITY_SNI_POOL
    assert len(settings.reality_sni_pool) >= 10
    assert len(settings.reality_sni_pool) == len(set(settings.reality_sni_pool))


def test_reality_sni_pool_normalizes_and_deduplicates():
    settings = General(reality_sni_pool=[" WWW.Example.COM ", "www.example.com", "example.org"])
    assert settings.reality_sni_pool == ["www.example.com", "example.org"]


def test_reality_sni_pool_rejects_url_and_port():
    for value in ["https://example.com", "example.com:443", "example.com/path"]:
        try:
            General(reality_sni_pool=[value])
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid SNI to be rejected: {value}")
