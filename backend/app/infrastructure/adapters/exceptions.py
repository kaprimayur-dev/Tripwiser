"""Railway data source adapter exceptions."""

class SourceAdapterError(Exception):
    """Base exception for all railway source adapter operations."""
    pass


class SourceFileNotFoundError(SourceAdapterError):
    """Raised when the specified source file does not exist on disk."""
    pass


class SourceIOError(SourceAdapterError):
    """Raised when an I/O error occurs while accessing or reading the source file."""
    pass


class SourceEncodingError(SourceAdapterError):
    """Raised when the source file cannot be decoded as valid UTF-8."""
    pass


class MalformedSourceError(SourceAdapterError):
    """Raised when the source file is not valid JSON or violates top-level GeoJSON schema."""
    pass

