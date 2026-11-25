"""Layered configuration merging primitives."""

from .merge import (
    deep_copy,
    merge,
    merge_all,
    merge_batch,
    merge_dict,
    merge_list,
    merge_scalar,
    validate_result,
)

__all__ = [
    "deep_copy",
    "merge_dict",
    "merge_list",
    "merge_scalar",
    "merge",
    "merge_all",
    "validate_result",
    "merge_batch",
]