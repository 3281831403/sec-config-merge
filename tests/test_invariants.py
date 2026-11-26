"""Regression tests for the layered configuration merge invariants.

Covers the incident scenario (an empty tenant overlay must not disable a
platform-level audit switch) and every invariant from the task statement:
deep recursive merge, list append/replace policies, empty-value policy,
input immutability at every layer, case-sensitive keys, associativity and
independence of batch entries.
"""

import copy

import pytest

from cfgmerge import (
    deep_copy,
    merge,
    merge_all,
    merge_batch,
    merge_dict,
    merge_list,
    merge_scalar,
)

APPEND_KEEP = {"list": "append", "empty": "keep"}
REPLACE_KEEP = {"list": "replace", "empty": "keep"}
REPLACE_OVERWRITE = {"list": "replace", "empty": "overwrite"}
APPEND_OVERWRITE = {"list": "append", "empty": "overwrite"}


# --- The incident itself ----------------------------------------------------

def test_empty_tenant_overlay_keeps_platform_audit_switch():
    platform = {
        "audit": {"enabled": True, "sink": "soc"},
        "tenants": {"t1": {"quota": 10}},
    }
    tenant = {"audit": {}, "tenants": {"t1": {}}}

    merged = merge(platform, tenant, REPLACE_KEEP)

    assert merged == platform
    assert merged["audit"]["enabled"] is True
    assert merged["tenants"]["t1"] == {"quota": 10}


def test_deep_nested_empty_dicts_do_not_erase_any_layer():
    left = {"a": {"b": {"c": {"d": 1}}}}
    right = {"a": {"b": {"c": {}}}}

    merged = merge(left, right, REPLACE_KEEP)

    assert merged == {"a": {"b": {"c": {"d": 1}}}}


def test_deep_merge_recurses_through_every_layer():
    left = {"svc": {"host": "h", "opts": {"debug": True, "retries": 3}}}
    right = {"svc": {"opts": {"retries": 5, "timeout": 9}}}

    merged = merge(left, right, REPLACE_KEEP)

    assert merged == {
        "svc": {"host": "h", "opts": {"debug": True, "retries": 5, "timeout": 9}}
    }


# --- List policies -----------------------------------------------------------

def test_append_policy_concatenates_in_left_right_order():
    left = {"tags": ["a", "b"]}
    right = {"tags": ["c", "d"]}

    merged = merge(left, right, APPEND_KEEP)

    assert merged == {"tags": ["a", "b", "c", "d"]}


def test_append_policy_works_through_merge_list_directly():
    assert merge_list([1, 2], [3], APPEND_KEEP) == [1, 2, 3]


def test_replace_policy_discards_left_list():
    merged = merge({"tags": [1, 2]}, {"tags": [3]}, REPLACE_KEEP)
    assert merged == {"tags": [3]}


def test_nested_lists_follow_policy_at_their_own_level():
    left = {"svc": {"routes": ["/a"]}}
    right = {"svc": {"routes": ["/b"]}}

    assert merge(left, right, APPEND_KEEP) == {"svc": {"routes": ["/a", "/b"]}}
    assert merge(left, right, REPLACE_KEEP) == {"svc": {"routes": ["/b"]}}


# --- Empty value policy ------------------------------------------------------

def test_none_and_empty_string_keep_left_by_default():
    left = {"a": "x", "b": "y", "c": 0}
    right = {"a": None, "b": "", "c": None}

    merged = merge(left, right, REPLACE_KEEP)

    assert merged == {"a": "x", "b": "y", "c": 0}


def test_overwrite_policy_lets_both_none_and_empty_string_win():
    left = {"a": "x", "b": "y"}
    right = {"a": None, "b": ""}

    merged = merge(left, right, REPLACE_OVERWRITE)

    assert merged == {"a": None, "b": ""}


def test_append_mode_combines_with_empty_overwrite():
    left = {"tags": ["a"], "name": "n"}
    right = {"tags": ["b"], "name": ""}

    merged = merge(left, right, APPEND_OVERWRITE)

    assert merged == {"tags": ["a", "b"], "name": ""}


def test_merge_scalar_directly_honours_policy():
    assert merge_scalar("old", "", REPLACE_KEEP) == "old"
    assert merge_scalar("old", "", REPLACE_OVERWRITE) == ""
    assert merge_scalar("old", None, REPLACE_KEEP) == "old"
    assert merge_scalar("old", None, REPLACE_OVERWRITE) is None
    assert merge_scalar("old", "new", REPLACE_KEEP) == "new"


# --- Immutability -------------------------------------------------------------

def test_inputs_untouched_with_nested_containers_and_append():
    left = {"app": {"retries": 1, "tls": {"verify": True}}, "routes": ["a"]}
    right = {"app": {"timeout": 5, "tls": {"ca": "x"}}, "routes": ["b"]}
    left_before = copy.deepcopy(left)
    right_before = copy.deepcopy(right)

    merged = merge(left, right, APPEND_KEEP)

    assert left == left_before
    assert right == right_before
    # Mutating the result must not feed back into either input.
    merged["app"]["tls"]["verify"] = False
    merged["routes"].append("z")
    assert left == left_before
    assert right == right_before


def test_deep_copy_is_independent_at_every_level():
    original = {"a": {"b": [1, {"c": 2}]}}
    duplicate = deep_copy(original)
    duplicate["a"]["b"][1]["c"] = 99
    assert original["a"]["b"][1]["c"] == 2


def test_empty_overlay_result_does_not_alias_input():
    left = {"a": {"b": 1}}
    right = {"a": {}}
    merged = merge(left, right, REPLACE_KEEP)
    merged["a"]["b"] = 2
    assert left["a"]["b"] == 1


def test_policy_mapping_is_not_mutated():
    policy = {"list": "append", "empty": "keep"}
    before = dict(policy)
    merge({"x": [1]}, {"x": [2]}, policy)
    assert policy == before


# --- Case sensitivity ----------------------------------------------------------

def test_keys_are_case_sensitive():
    left = {"Key": 1, "KEY": 2}
    right = {"key": 3, "Key": 4}

    merged = merge(left, right, REPLACE_KEEP)

    assert merged == {"Key": 4, "KEY": 2, "key": 3}


def test_nested_case_sensitive_keys_keep_their_spelling():
    merged = merge_dict({"A": {"B": 1}}, {"A": {"b": 2, "B": 3}}, REPLACE_KEEP)
    assert merged == {"A": {"B": 3, "b": 2}}


# --- Associativity and determinism ----------------------------------------------

POLICIES = [APPEND_KEEP, REPLACE_KEEP, REPLACE_OVERWRITE, APPEND_OVERWRITE]


@pytest.mark.parametrize("policy", POLICIES)
def test_merge_is_associative(policy):
    x = {"a": {"k": 1}, "tags": [1], "name": "x"}
    y = {"a": {"m": 2}, "tags": [2], "name": ""}
    z = {"a": {"k": 3}, "tags": [3], "name": None}

    left_assoc = merge(merge(x, y, policy), z, policy)
    right_assoc = merge(x, merge(y, z, policy), policy)

    assert left_assoc == right_assoc


@pytest.mark.parametrize("policy", POLICIES)
def test_merge_all_preserves_caller_order_and_matches_pairwise(policy):
    layers = [
        {"audit": {"enabled": True}},
        {"audit": {"sink": "soc"}},
        {"audit": {}, "extra": [1]},
    ]
    pairwise = {}
    for layer in layers:
        pairwise = merge(pairwise, layer, policy)

    assert merge_all(layers, policy) == pairwise


def test_merge_all_order_changes_where_order_matters():
    first = {"v": 1}
    second = {"v": 2}
    assert merge_all([first, second], REPLACE_KEEP) == {"v": 2}
    assert merge_all([second, first], REPLACE_KEEP) == {"v": 1}


# --- Type mismatch and edge shapes ----------------------------------------------

def test_container_replaces_incompatible_left_type():
    assert merge({"x": 1}, {"x": {"y": 2}}, REPLACE_KEEP) == {"x": {"y": 2}}
    assert merge({"x": {"y": 2}}, {"x": [1]}, REPLACE_KEEP) == {"x": [1]}
    assert merge({"x": [1]}, {"x": "s"}, REPLACE_KEEP) == {"x": "s"}


def test_empty_inputs_are_handled_without_aliasing():
    assert merge({}, {}, REPLACE_KEEP) == {}
    assert merge({}, {"a": 1}, REPLACE_KEEP) == {"a": 1}
    assert merge({"a": 1}, {}, REPLACE_KEEP) == {"a": 1}
    merged = merge({"a": 1}, {}, REPLACE_KEEP)
    merged["b"] = 2
    assert merge({"a": 1}, {}, REPLACE_KEEP) == {"a": 1}


# --- Batch independence -----------------------------------------------------------

def test_batch_entries_are_fully_independent():
    pairs = {
        "dev": ({"db": {"host": "dev"}}, {"db": {"port": 5432}}),
        "prod": ({"db": {"host": "prod"}}, {"db": {"port": 5433}}),
    }

    batch = merge_batch(pairs, REPLACE_KEEP)

    assert batch["dev"] == {"db": {"host": "dev", "port": 5432}}
    assert batch["prod"] == {"db": {"host": "prod", "port": 5433}}

    batch["dev"]["db"]["host"] = "mutated"
    fresh = merge_batch(pairs, REPLACE_KEEP)
    assert fresh["dev"]["db"]["host"] == "dev"


def test_batch_does_not_mutate_its_input_pairs():
    pairs = {"a": ({"k": [1]}, {"k": [2]})}
    before = copy.deepcopy(pairs)
    merge_batch(pairs, APPEND_KEEP)
    assert pairs == before
