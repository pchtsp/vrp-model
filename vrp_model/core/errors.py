"""Domain-specific exceptions."""


class VRPModelError(Exception):
    """Base error for vrp_model."""


class ValidationError(VRPModelError):
    """Model failed structure, consistency, or feasibility validation."""


class SolverCapabilityError(VRPModelError):
    """Solver does not support one or more features present on the model."""


class SolverNotInstalledError(VRPModelError):
    """Optional solver dependency is not installed."""


class MappingError(VRPModelError):
    """Canonical model ↔ solver-native conversion failed."""
