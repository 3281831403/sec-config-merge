import copy

from cfgmerge import merge, merge_batch

REPLACE = {"list": "replace", "empty": "keep"}
OVERWRITE = {"list": "replace", "empty": "overwrite"}


def test_two_level_dict_merge():
    left = {"service": {"host": "10.0.0.1", "options": {"debug": True}}}
    right = {"service": {"options": {}}}

    merged = merge(left, right, REPLACE)

    assert merged.get("service") == {
        "host": "10.0.0.1",
        "options": {"debug": True},
    }


def test_list_replace_policy():
    left = {"Tags": ["alpha", "beta"]}
    right = {"Tags": ["gamma"]}

    merged = merge(left, right, REPLACE)

    assert merged == {"Tags": ["gamma"]}


def test_scalar_overwrite_policy():
    left = {"label": "primary"}
    right = {"label": ""}

    merged = merge(left, right, OVERWRITE)

    assert merged.get("label") == ""


def test_inputs_are_not_modified():
    left = {"app": {"retries": 1}, "routes": ["a"]}
    right = {"app": {"timeout": 5}, "routes": ["b"]}
    left_before = copy.deepcopy(left)
    right_before = copy.deepcopy(right)

    merge(left, right, REPLACE)

    assert left == left_before
    assert right == right_before


def test_batch_entries_are_independent():
    pairs = {
        "dev": ({"db": {"host": "dev"}}, {"db": {"port": 5432}}),
        "prod": ({"db": {"host": "prod"}}, {"db": {"port": 5433}}),
    }

    batch = merge_batch(pairs, REPLACE)

    assert batch["dev"].get("db") == {"host": "dev", "port": 5432}
    assert batch["prod"].get("db") == {"host": "prod", "port": 5433}