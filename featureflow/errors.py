from __future__ import annotations


class PathNotAllowedError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class DiffTooLargeError(Exception):
    pass


class PatchApplyError(Exception):
    pass

