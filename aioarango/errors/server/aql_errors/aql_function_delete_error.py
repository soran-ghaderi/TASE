from aioarango.errors.base import ArangoServerError


class AQLFunctionDeleteError(ArangoServerError):
    """Failed to delete AQL user function."""
