"""Smoke tests for package import."""


def test_public_api_imports() -> None:
    from raindrop_replicate import (
        AuthenticationError,
        LedgerFormatError,
        RaindropAPIError,
        RaindropReplicateError,
        RaindropResponseError,
        ReplicationResult,
        StorageConsistencyError,
        replicate,
    )

    assert RaindropReplicateError is not None
    assert AuthenticationError is not None
    assert RaindropAPIError is not None
    assert RaindropResponseError is not None
    assert LedgerFormatError is not None
    assert StorageConsistencyError is not None
    assert ReplicationResult is not None
    assert replicate is not None
