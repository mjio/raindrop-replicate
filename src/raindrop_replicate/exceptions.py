"""Exception hierarchy for raindrop-replicate."""


class RaindropReplicateError(Exception):
    """Base exception for this library."""


class AuthenticationError(RaindropReplicateError):
    """Authentication or authorization failure."""


class RaindropAPIError(RaindropReplicateError):
    """Raindrop API request failed."""


class RaindropResponseError(RaindropReplicateError):
    """Raindrop API response was malformed or invalid."""


class LedgerFormatError(RaindropReplicateError):
    """Ledger file is invalid or unsupported."""


class StorageConsistencyError(RaindropReplicateError):
    """Local storage state is inconsistent."""
