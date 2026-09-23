class ProjectorError(Exception):
    """Base error for Actor 7."""


class UnsupportedProjectionFact(ProjectorError):
    pass


class MissingCanonicalDependency(ProjectorError):
    pass


class InconsistentCanonicalState(ProjectorError):
    pass


class StaleUniverseProjection(ProjectorError):
    pass
