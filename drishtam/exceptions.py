# DRISHTAM Exceptions
"""Custom exception hierarchy for DRISHTAM.

All DRISHTAM-specific exceptions inherit from DrishtamError.
Use these instead of generic ValueError/RuntimeError for better error handling.
"""

from __future__ import annotations


class DrishtamError(Exception):
    """Base exception for all DRISHTAM errors."""


class DataValidationError(DrishtamError):
    """Raised when data fails validation or quality checks.

    Examples:
        - Required columns missing from DataFrame
        - Values outside expected ranges
        - Null values in non-nullable columns
        - Record count doesn't match expectations
    """


class ModelNotTrainedError(DrishtamError):
    """Raised when attempting inference on an untrained model.

    Examples:
        - Calling predict() before train()
        - Loading a model checkpoint that doesn't exist
    """


class InsufficientDataError(DrishtamError):
    """Raised when data is too sparse for reliable computation.

    Examples:
        - Too few violations in a grid cell for density computation
        - Too few events for correlation analysis
        - Empty road network after filtering
    """


class ConfigurationError(DrishtamError):
    """Raised when configuration is invalid or incomplete.

    Examples:
        - Missing required config file
        - Invalid weight configuration (doesn't sum to 1.0)
        - Unknown road tier or vehicle type
    """


class GraphConstructionError(DrishtamError):
    """Raised when graph construction fails.

    Examples:
        - OSM network has no edges in specified area
        - Line graph transformation produces disconnected graph
        - Node features have incompatible dimensions
    """
