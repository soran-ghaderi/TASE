from aioarango.errors.server import ArangoServerError


class DocumentInError(ArangoServerError):
    """Failed to check whether document exists."""
