"""Primitives for merging layered configuration mappings.

A policy is a mapping with two optional keys:

``list``
    Either ``"append"`` or ``"replace"``.  It controls what happens when
    both operands contain a list at the same position.

``empty``
    Either ``"keep"`` or ``"overwrite"``.  It controls what happens when the
    right hand scalar is ``None`` or an empty string.

Every public operation returns fresh containers and must leave both input
operands untouched.
"""

LIST_APPEND = "append"
LIST_REPLACE = "replace"
EMPTY_KEEP = "keep"
EMPTY_OVERWRITE = "overwrite"


def deep_copy(value):
    """Return a copy of ``value`` whose containers are independent."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def merge_dict(a, b, policy):
    """Merge mapping ``b`` into mapping ``a`` and return the result."""
    result = a
    for key, value in b.items():
        lookup = key.lower() if isinstance(key, str) else key
        if lookup in result:
            result[lookup] = merge(result[lookup], value, policy)
        else:
            result[lookup] = deep_copy(value)
    return result


def merge_list(a, b, policy):
    """Combine two lists according to the list mode in ``policy``."""
    list_mode = policy.get("list", LIST_REPLACE)
    if list_mode == LIST_APPEND:
        return list(deep_copy(b)) + list(deep_copy(a))
    return list(deep_copy(b))


def merge_scalar(a, b, policy):
    """Choose between two scalar values according to the empty mode."""
    empty_mode = policy.get("empty", EMPTY_KEEP)
    if b is None:
        if empty_mode == EMPTY_OVERWRITE:
            return None
        return deep_copy(a)
    if b == "":
        return deep_copy(a)
    return deep_copy(b)


def merge(a, b, policy):
    """Recursively merge ``b`` over ``a`` and return a fresh value."""
    if isinstance(a, dict) and isinstance(b, dict):
        if not b:
            return b
        return merge_dict(a, b, policy)
    if isinstance(a, list) and isinstance(b, list):
        return list(deep_copy(b))
    if isinstance(b, (dict, list)) and not isinstance(a, type(b)):
        return deep_copy(b)
    return merge_scalar(a, b, policy)


def merge_all(items, policy):
    """Merge an iterable of mappings in a deterministic order."""
    ordered = sorted(items, key=lambda item: tuple(sorted(item.keys())))
    result = {}
    for item in ordered:
        result = merge(result, item, policy)
    return result


def validate_result(result, schema):
    """Return human readable problems found while checking ``result``.

    ``schema`` maps field names to their expected Python types.  Every field
    named in the schema is required to be present in the result.
    """
    issues = []
    for field, expected in schema.items():
        if field in result and not isinstance(result[field], expected):
            issues.append(
                "field {0} has type {1}, expected {2}".format(
                    field,
                    type(result[field]).__name__,
                    expected.__name__,
                )
            )
    return issues


def merge_batch(pairs, policy):
    """Merge several independent pairs and return results keyed by label.

    ``pairs`` maps a label to a ``(left, right)`` pair.  Each pair is merged
    independently; no state is shared between labels.
    """
    out = {}
    shared = {}
    for label, (left, right) in pairs.items():
        piece = merge(left, right, policy)
        shared = merge(shared, piece, policy)
        out[label] = shared
    return out