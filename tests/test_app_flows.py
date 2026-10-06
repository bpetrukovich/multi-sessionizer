"""App wiring tests with fake adapters (FR-018/FR-020, US1/US3/US4).

Injects fake adapters into ``FlowDeps`` and asserts the wiring sequence with no
real subprocess/filesystem/environment/terminal side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from multi_sessionizer.app.configuration import Config, ConfigError, ConfigNotFoundError
from multi_sessionizer.app.flows import (
    add_external_flow,
    delete_external_flow,
    external_label,
    interactive_flow,
    list_external_flow,
    run_selection,
    session_flow,
    switch_flow,
)
from multi_sessionizer.app.ports import (
    ExternalAddResult,
    ExternalDeleteResult,
    ExternalStoreError,
    FlowDeps,
)
from multi_sessionizer.domain.external import deletion_key
from multi_sessionizer.domain.models import (
    Command,
    CommandPlan,
    RuntimeSnapshot,
    Selection,
    SessionEntry,
)
from multi_sessionizer.domain.workspace import desired_name, fingerprint

WS_DEF = "session_name: myws\nwindows:\n  - shell_command: vim\n"
BAD_WS = "windows: []\n"
GRP_DEF = "name: ext-stack\nsessions:\n  - /p/b\n"


def ws_entry(definition=WS_DEF):
    return SessionEntry(kind="workspace", definition=definition)


def dir_entry(path):
    return SessionEntry(kind="directory", path=path)


def group_entry(name, members):
    return SessionEntry(kind="group", name=name, members=tuple(members))


def cmd(program, *args, input=None):
    return Command(program, args, input=input)


class FakeConfigLoader:
    def __init__(self, cfg=None):
        self.calls: list[str] = []
        self.cfg = cfg if cfg is not None else Config()
        self.missing = []
        self.not_found: ConfigNotFoundError | None = None
        self.cfg_error: ConfigError | None = None

    def load(self) -> Config:
        self.calls.append("load")
        if self.not_found is not None:
            raise self.not_found
        if self.cfg_error is not None:
            raise self.cfg_error
        return self.cfg

    def missing_dirs(self, cfg):
        self.calls.append("missing_dirs")
        return self.missing


class FakeDiscovery:
    def __init__(self, dirs=()):
        self.calls: list[str] = []
        self.dirs = list(dirs)

    def collect_dirs(self, cfg):
        self.calls.append("collect_dirs")
        return self.dirs


class FakeScorer:
    def __init__(self, text=""):
        self.calls: list[str] = []
        self.text = text

    def scores(self) -> str:
        self.calls.append("scores")
        return self.text


class FakePicker:
    def __init__(self, selected=None):
        self.calls: list[str] = []
        self.selected = selected if selected is not None else []

    def pick(self, items: list[str]) -> list[str]:
        self.calls.append("pick")
        self.items = items
        return self.selected


class FakeClassifier:
    def __init__(self, selection=None, classified=([], [])):
        self.calls: list[str] = []
        self.selection = selection if selection is not None else Selection((), ())
        self.classified = classified
        self.lines = []

    def classify_args(self, argv: Sequence[str]):
        self.calls.append("classify_args")
        return self.classified

    def classify_selection(self, lines: list[str]) -> Selection:
        self.calls.append("classify_selection")
        self.lines = lines
        return self.selection


class FakeProbe:
    def __init__(self, snapshot=None):
        self.calls: list[str] = []
        self.snapshot_value = (
            snapshot if snapshot is not None else RuntimeSnapshot(False, False, {})
        )

    def snapshot(self) -> RuntimeSnapshot:
        self.calls.append("snapshot")
        return self.snapshot_value


class FakeExecutor:
    def __init__(self):
        self.calls: list[str] = []
        self.plans: list[CommandPlan] = []

    def execute(self, cmds: CommandPlan) -> None:
        self.calls.append("execute")
        self.plans.append(cmds)


class FakeMessages:
    def __init__(self):
        self.calls: list[str] = []
        self.config_path = None
        self.missing = []
        self.problems = []
        self.errors = []
        self.added = []
        self.list_rows = []
        self.deleted = []
        self.empty_calls = 0

    def config_not_found(self, path: object) -> None:
        self.calls.append("config_not_found")
        self.config_path = path

    def missing_dirs(self, missing_dirs: list[str]) -> None:
        self.calls.append("missing_dirs")
        self.missing = missing_dirs

    def workspace_problems(self, problems: list[str]) -> None:
        self.calls.append("workspace_problems")
        self.problems = problems

    def error(self, msg: str) -> None:
        self.calls.append("error")
        self.errors.append(msg)

    def external_added(self, label: str) -> None:
        self.calls.append("external_added")
        self.added.append(label)

    def external_list(self, rows: list[tuple[str, str, str]]) -> None:
        self.calls.append("external_list")
        self.list_rows = rows

    def external_deleted(self, message: str) -> None:
        self.calls.append("external_deleted")
        self.deleted.append(message)

    def external_empty(self) -> None:
        self.calls.append("external_empty")
        self.empty_calls += 1


class FakeExternalStore:
    def __init__(self, entries=()):
        self.calls: list[str] = []
        self.entries = list(entries)
        self.add_results = []
        self.delete_results = []
        self.error: Exception | None = None

    def add(self, entry: SessionEntry):
        self.calls.append("add")
        if self.error is not None:
            raise self.error
        result = self.add_results.pop(0) if self.add_results else None
        if result is not None:
            return result
        self.entries.append(entry)
        return ExternalAddResult(ok=True, entry=entry)

    def delete(self, key: str):
        self.calls.append("delete")
        if self.error is not None:
            raise self.error
        result = self.delete_results.pop(0) if self.delete_results else None
        if result is not None:
            return result
        return ExternalDeleteResult(ok=True, message=f"Deleted external entry '{key}'.")

    def list_entries(self):
        self.calls.append("list_entries")
        if self.error is not None:
            raise self.error
        return tuple(self.entries)


def make_deps(**kw):
    kw.setdefault("config_loader", FakeConfigLoader())
    kw.setdefault("discovery", FakeDiscovery())
    kw.setdefault("scorer", FakeScorer())
    kw.setdefault("picker", FakePicker())
    kw.setdefault("classifier", FakeClassifier())
    kw.setdefault("probe", FakeProbe())
    kw.setdefault("executor", FakeExecutor())
    kw.setdefault("messages", FakeMessages())
    kw.setdefault("external_store", FakeExternalStore())
    return FlowDeps(**kw)


def test_interactive_flow_calls_sequence():
    plan = CommandPlan(
        [
            cmd("zoxide", "add", "/a/one"),
            cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
            cmd("tmux", "attach", "-t", "one"),
        ]
    )
    deps = make_deps(
        config_loader=FakeConfigLoader(),
        discovery=FakeDiscovery(dirs=["/a/one"]),
        scorer=FakeScorer("10.0 /a/one\n"),
        picker=FakePicker(selected=["/a/one"]),
        classifier=FakeClassifier(selection=Selection(("/a/one",), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert deps.config_loader.calls == ["load", "missing_dirs"]
    assert deps.discovery.calls == ["collect_dirs"]
    assert deps.scorer.calls == ["scores"]
    assert deps.picker.calls == ["pick"]
    assert deps.classifier.calls == ["classify_selection"]
    assert deps.probe.calls == ["snapshot"]
    assert deps.executor.calls == ["execute"]
    assert deps.executor.plans == [plan]
    assert deps.picker.items == ["/a/one"]


def test_switch_flow_uses_classifier_probe_executor():
    plan = CommandPlan(
        [
            cmd("zoxide", "add", "/a/one"),
            cmd("tmux", "attach", "-t", "one"),
        ]
    )
    deps = make_deps(
        classifier=FakeClassifier(classified=(["/a/one"], [])),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, True, {"one": "/a/one"})),
        executor=FakeExecutor(),
    )
    assert switch_flow(["/a/one"], deps) == 0
    assert deps.classifier.calls == ["classify_args"]
    assert deps.probe.calls == ["snapshot"]
    assert deps.executor.calls == ["execute"]
    assert deps.executor.plans == [plan]


def test_switch_flow_bad_path_reports_error_and_returns_1():
    class RaisingClassifier:
        def classify_args(self, argv: Sequence[str]):
            raise ValueError("Not a directory or file: /nope")

    deps = make_deps(
        classifier=RaisingClassifier(),
        probe=FakeProbe(),
        executor=FakeExecutor(),
        messages=FakeMessages(),
    )
    assert switch_flow(["/nope"], deps) == 1
    assert deps.messages.errors == ["Not a directory or file: /nope"]
    assert deps.probe.calls == []
    assert deps.executor.calls == []


def test_run_selection_produces_expected_plan_no_subprocess():
    selection = Selection(("/a/one",), ())
    snapshot = RuntimeSnapshot(False, False, {})
    deps = make_deps(probe=FakeProbe(snapshot=snapshot), executor=FakeExecutor())
    assert run_selection(selection, deps) == 0
    assert deps.executor.plans == [
        CommandPlan(
            [
                cmd("zoxide", "add", "/a/one"),
                cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
                cmd("tmux", "attach", "-t", "one"),
            ]
        )
    ]


def test_config_not_found_returns_one():
    loader = FakeConfigLoader()
    loader.not_found = ConfigNotFoundError(Path("/nope.toml"))
    messages = FakeMessages()
    deps = make_deps(config_loader=loader, messages=messages)
    assert interactive_flow(deps) == 1
    assert messages.calls == ["config_not_found"]
    assert messages.config_path is loader.not_found


def test_missing_dirs_returns_one():
    loader = FakeConfigLoader()
    loader.missing = ["/nodir"]
    messages = FakeMessages()
    deps = make_deps(config_loader=loader, messages=messages)
    assert interactive_flow(deps) == 1
    assert messages.calls == ["missing_dirs"]
    assert messages.missing == ["/nodir"]


def test_empty_picker_selection_returns_zero_executor_not_called():
    deps = make_deps(picker=FakePicker(selected=[]), executor=FakeExecutor())
    assert interactive_flow(deps) == 0
    assert deps.executor.calls == []


def test_interactive_flow_lists_workspace_labels_and_builds_selection():
    loader = FakeConfigLoader(cfg=Config(sessions=(ws_entry(),)))
    executor = FakeExecutor()
    deps = make_deps(
        config_loader=loader,
        picker=FakePicker(selected=["[tmuxp] myws"]),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=executor,
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == ["[tmuxp] myws"]
    assert deps.classifier.calls == ["classify_selection"]
    assert executor.plans == [
        CommandPlan(
            [
                cmd("tmuxp", "load", "-d", "--no-progress", "-s", "myws", input=WS_DEF),
                cmd(
                    "tmux",
                    "set-option",
                    "-t",
                    "myws",
                    "@multi-sessionizer-marker",
                    fingerprint(WS_DEF),
                ),
                cmd("tmux", "attach", "-t", "myws"),
            ]
        )
    ]


def test_interactive_flow_splits_workspace_labels_from_dir_lines():
    loader = FakeConfigLoader(cfg=Config(sessions=(ws_entry(),)))
    executor = FakeExecutor()
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=["/a/one"]),
        picker=FakePicker(selected=["/a/one", "[tmuxp] myws"]),
        classifier=FakeClassifier(selection=Selection(("/a/one",), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=executor,
    )
    assert interactive_flow(deps) == 0
    assert executor.plans == [
        CommandPlan(
            [
                cmd("zoxide", "add", "/a/one"),
                cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
                cmd("tmuxp", "load", "-d", "--no-progress", "-s", "myws", input=WS_DEF),
                cmd(
                    "tmux",
                    "set-option",
                    "-t",
                    "myws",
                    "@multi-sessionizer-marker",
                    fingerprint(WS_DEF),
                ),
                cmd("tmux", "attach", "-t", "one"),
            ]
        )
    ]


def test_full_wiring_replaceable_executor(monkeypatch, tmp_path):
    from multi_sessionizer.infrastructure.classifier import PathSelectionClassifier
    from multi_sessionizer.infrastructure.config_loader import FileConfigLoader
    from multi_sessionizer.infrastructure.discovery import FileCandidateDiscovery

    project = tmp_path / "projects" / "one"
    project.mkdir(parents=True)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(f'sessions = ["{project}"]\n')
    monkeypatch.setenv("MULTI_SESSIONIZER_CONFIG", str(cfg_path))

    deps = FlowDeps(
        config_loader=FileConfigLoader(),
        discovery=FileCandidateDiscovery(),
        scorer=FakeScorer("10.0 /a/one\n"),
        picker=FakePicker(selected=[str(project)]),
        classifier=PathSelectionClassifier(),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=FakeExecutor(),
        messages=FakeMessages(),
        external_store=FakeExternalStore(),
    )
    assert interactive_flow(deps) == 0
    assert deps.executor.plans == [
        CommandPlan(
            [
                cmd("zoxide", "add", str(project)),
                cmd("tmux", "new-session", "-ds", "one", "-c", str(project)),
                cmd("tmux", "attach", "-t", "one"),
            ]
        )
    ]


def test_full_wiring_run_selection_with_real_classifier(monkeypatch, tmp_path):
    from multi_sessionizer.infrastructure.classifier import PathSelectionClassifier

    project = tmp_path / "projects" / "one"
    project.mkdir(parents=True)
    classifier = PathSelectionClassifier()
    selection = classifier.classify_selection([str(project)])
    deps = make_deps(
        classifier=classifier,
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=FakeExecutor(),
    )
    assert run_selection(selection, deps) == 0
    assert deps.executor.plans == [
        CommandPlan(
            [
                cmd("zoxide", "add", str(project)),
                cmd("tmux", "new-session", "-ds", "one", "-c", str(project)),
                cmd("tmux", "attach", "-t", "one"),
            ]
        )
    ]


def test_session_flow_valid_workspace_provisions():
    executor = FakeExecutor()
    deps = make_deps(
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=executor,
    )
    assert session_flow([WS_DEF], deps) == 0
    assert executor.plans == [
        CommandPlan(
            [
                cmd("tmuxp", "load", "-d", "--no-progress", "-s", "myws", input=WS_DEF),
                cmd(
                    "tmux",
                    "set-option",
                    "-t",
                    "myws",
                    "@multi-sessionizer-marker",
                    fingerprint(WS_DEF),
                ),
                cmd("tmux", "attach", "-t", "myws"),
            ]
        )
    ]


def test_session_flow_invalid_workspace_reports_and_skips_execution():
    messages = FakeMessages()
    executor = FakeExecutor()
    deps = make_deps(messages=messages, executor=executor)
    assert session_flow([BAD_WS], deps) == 1
    assert messages.calls == ["workspace_problems"]
    assert "windows" in " ".join(messages.problems)
    assert executor.calls == []
    assert deps.probe.calls == []


def test_session_flow_multiple_workspaces_validate_all():
    messages = FakeMessages()
    deps = make_deps(messages=messages, executor=FakeExecutor())
    assert session_flow([WS_DEF, BAD_WS], deps) == 1
    assert messages.calls == ["workspace_problems"]
    assert len(messages.problems) >= 1


def test_run_selection_reports_provisioning_error():
    class BoomExecutor:
        def execute(self, cmds: CommandPlan) -> None:
            raise ProvisioningError(
                "tmuxp is required for workspace sessions but was not found on PATH."
            )

    from multi_sessionizer.domain.run import ProvisioningError

    messages = FakeMessages()
    deps = make_deps(
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=BoomExecutor(),
        messages=messages,
    )
    assert run_selection(Selection((), (WS_DEF,)), deps) == 1
    assert messages.calls == ["error"]
    assert "tmuxp is required" in messages.errors[0]


def test_unified_picker_mixes_dir_tmuxp_and_group_lines():
    g = group_entry("stack", [dir_entry("/tmp/b"), ws_entry()])
    loader = FakeConfigLoader(
        cfg=Config(
            sessions=(
                dir_entry("/tmp/a"),
                ws_entry(),
                g,
            )
        )
    )
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == ["/tmp/a", "[tmuxp] myws", "[group] stack"]


def test_selecting_group_expands_to_flat_selection():
    g = group_entry(
        "stack",
        [dir_entry("/tmp/b"), ws_entry(), dir_entry("/tmp/c")],
    )
    loader = FakeConfigLoader(cfg=Config(sessions=(g,)))
    executor = FakeExecutor()
    deps = make_deps(
        config_loader=loader,
        picker=FakePicker(selected=["[group] stack"]),
        classifier=FakeClassifier(selection=Selection(("/tmp/b", "/tmp/c"), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=executor,
    )
    assert interactive_flow(deps) == 0
    assert deps.classifier.calls == ["classify_selection"]
    assert deps.classifier.lines == ["/tmp/b", "/tmp/c"]
    assert executor.calls == ["execute"]


def test_duplicate_group_names_are_disambiguated_and_selectable():
    g1 = group_entry("stack", [dir_entry("/tmp/a")])
    g2 = group_entry("stack", [dir_entry("/tmp/b")])
    loader = FakeConfigLoader(cfg=Config(sessions=(g1, g2)))
    executor = FakeExecutor()
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        picker=FakePicker(selected=["[group] stack-2"]),
        classifier=FakeClassifier(selection=Selection(("/tmp/b",), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=executor,
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == ["[group] stack", "[group] stack-2"]
    assert deps.classifier.lines == ["/tmp/b"]
    assert executor.calls == ["execute"]


def test_interactive_flow_group_with_tags_renders_tag_prefixes():
    g = SessionEntry(kind="group", name="stack", tags=("pp-1",), members=(dir_entry("/tmp/a"),))
    loader = FakeConfigLoader(cfg=Config(sessions=(g,)))
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        picker=FakePicker(selected=["[group] [pp-1] stack"]),
        classifier=FakeClassifier(selection=Selection(("/tmp/a",), ())),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == ["[group] [pp-1] stack"]


def test_interactive_flow_external_tagged_entry_renders_tags():
    store = FakeExternalStore(
        entries=[SessionEntry(kind="directory", path="/x/y", tags=("pp-000000",))]
    )
    deps = make_deps(
        config_loader=FakeConfigLoader(cfg=Config(sessions=())),
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        picker=FakePicker(selected=[]),
        external_store=store,
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == ["[external] [pp-000000] /x/y"]


def test_config_error_surfaces_via_error_and_returns_one():
    loader = FakeConfigLoader(cfg=Config())
    loader.cfg_error = ConfigError(
        ["Group is missing a 'name'.", "Group 'g' has an empty 'sessions' list."]
    )
    messages = FakeMessages()
    deps = make_deps(config_loader=loader, messages=messages, executor=FakeExecutor())
    assert interactive_flow(deps) == 1
    assert messages.calls == ["error", "error"]
    assert messages.errors == [
        "Group is missing a 'name'.",
        "Group 'g' has an empty 'sessions' list.",
    ]
    assert deps.executor.calls == []


# --- User Story 1: external add ---------------------------------------------


@pytest.mark.parametrize(
    "arg, expected",
    [
        ("/x/y", dir_entry("/x/y")),
        (WS_DEF, ws_entry()),
        (GRP_DEF, group_entry("ext-stack", [dir_entry("/p/b")])),
    ],
)
def test_add_external_flow_valid_calls_store_and_confirms(arg, expected):
    store = FakeExternalStore()
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert add_external_flow(arg, deps) == 0
    assert store.calls == ["add"]
    assert store.entries == [expected]
    assert messages.calls == ["external_added"]
    assert messages.added == [deletion_key(expected)]


def test_add_external_flow_invalid_entry_reports_and_never_stores():
    store = FakeExternalStore()
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert add_external_flow("foo: bar\nbaz: 1\n", deps) == 1
    assert store.calls == []
    assert "error" in messages.calls
    assert len(messages.errors) == 1


def test_add_external_flow_with_cli_tags_stores_tagged_directory():
    store = FakeExternalStore()
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert add_external_flow("/x/y", deps, tags=("pp-000000",)) == 0
    assert store.entries == [SessionEntry(kind="directory", path="/x/y", tags=("pp-000000",))]
    assert messages.calls == ["external_added"]


def test_external_label_includes_tags():
    entry = SessionEntry(kind="directory", path="/x/y", tags=("pp-1", "backend"))
    assert external_label(entry) == "[external] [pp-1] [backend] /x/y"


def test_external_label_without_tags_is_unchanged():
    assert external_label(dir_entry("/x/y")) == "[external] /x/y"


def test_add_external_flow_duplicate_reports_error_and_returns_one():
    store = FakeExternalStore()
    store.add_results = [ExternalAddResult(ok=False, error="External entry already exists: /x/y.")]
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert add_external_flow("/x/y", deps) == 1
    assert store.calls == ["add"]
    assert "external_added" not in messages.calls
    assert messages.errors == ["External entry already exists: /x/y."]


# --- User Story 2: external list --------------------------------------------


def test_list_external_flow_nonempty_calls_external_list():
    store = FakeExternalStore(
        entries=[dir_entry("/x/y"), ws_entry(WS_DEF), group_entry("ext-stack", [dir_entry("/p/b")])]
    )
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert list_external_flow(deps) == 0
    assert store.calls == ["list_entries"]
    assert messages.calls == ["external_list"]
    assert messages.list_rows == [
        ("directory", "[external] /x/y", "/x/y"),
        ("workspace", f"[external] {desired_name(WS_DEF)}", desired_name(WS_DEF)),
        ("group", "[external] ext-stack", "ext-stack"),
    ]


def test_list_external_flow_empty_calls_external_empty():
    store = FakeExternalStore()
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert list_external_flow(deps) == 0
    assert messages.calls == ["external_empty"]
    assert "external_list" not in messages.calls


# --- User Story 3: external delete -------------------------------------------


def test_delete_external_flow_single_match_calls_store_delete():
    store = FakeExternalStore(entries=[dir_entry("/x/y")])
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert delete_external_flow("/x/y", deps) == 0
    assert store.calls == ["list_entries", "delete"]
    assert messages.calls == ["external_deleted"]
    assert len(messages.deleted) == 1


def test_delete_external_flow_not_found_reports_and_no_delete():
    store = FakeExternalStore(entries=[dir_entry("/x/y")])
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert delete_external_flow("/nope", deps) == 1
    assert store.calls == ["list_entries"]
    assert "delete" not in store.calls
    assert messages.errors == ["No external entry with deletion key '/nope'."]


def test_delete_external_flow_ambiguous_reports_matches_and_removes_none():
    ws1 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: one\n')
    ws2 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: two\n')
    store = FakeExternalStore(entries=[ws1, ws2])
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert delete_external_flow("shared", deps) == 1
    assert store.calls == ["list_entries"]
    assert "delete" not in store.calls
    assert "matches multiple entries" in messages.errors[0]


# --- User Story 4: picker integration ---------------------------------------


def test_interactive_flow_merges_external_candidates():
    store = FakeExternalStore(
        entries=[
            dir_entry("/ext/d"),
            ws_entry(WS_DEF),
            group_entry("ext-stack", [dir_entry("/p/b")]),
        ]
    )
    loader = FakeConfigLoader(cfg=Config(sessions=(dir_entry("/cfg/a"),)))
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        external_store=store,
        picker=FakePicker(selected=[]),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert deps.picker.items == [
        "/cfg/a",
        "[external] /ext/d",
        f"[external] {desired_name(WS_DEF)}",
        "[external] ext-stack",
    ]


def test_interactive_flow_mixed_external_and_config_routing():
    store = FakeExternalStore(entries=[dir_entry("/ext/d"), ws_entry(WS_DEF)])
    loader = FakeConfigLoader(cfg=Config(sessions=(dir_entry("/cfg/a"),)))
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        external_store=store,
        picker=FakePicker(
            selected=["/cfg/a", "[external] /ext/d", f"[external] {desired_name(WS_DEF)}"]
        ),
        classifier=FakeClassifier(selection=Selection(("/cfg/a", "/ext/d"), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert deps.classifier.calls == ["classify_selection"]
    assert deps.classifier.lines == ["/cfg/a", "/ext/d"]
    assert deps.executor.calls == ["execute"]
    assert len(deps.executor.plans) == 1
    assert fingerprint(WS_DEF) in {c.args[-1] for c in deps.executor.plans[0]}


def test_interactive_flow_corrupt_store_degrades_gracefully():
    store = FakeExternalStore()
    store.error = ExternalStoreError("file is not a database")
    loader = FakeConfigLoader(cfg=Config(sessions=(dir_entry("/cfg/a"),)))
    messages = FakeMessages()
    deps = make_deps(
        config_loader=loader,
        discovery=FakeDiscovery(dirs=[]),
        scorer=FakeScorer(""),
        external_store=store,
        messages=messages,
        picker=FakePicker(selected=[]),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert "External store error: file is not a database." in messages.errors
    assert deps.picker.items == ["/cfg/a"]


@pytest.mark.parametrize(
    "flow,args",
    [
        (add_external_flow, ("/x/y",)),
        (list_external_flow, ()),
        (delete_external_flow, ("/x/y",)),
    ],
)
def test_external_flows_report_corrupt_store_and_return_one(flow, args):
    store = FakeExternalStore()
    store.error = ExternalStoreError("file is not a database")
    messages = FakeMessages()
    deps = make_deps(external_store=store, messages=messages)
    assert flow(*args, deps) == 1
    assert messages.errors == ["External store error: file is not a database."]


def test_external_list_columns_are_separated_when_label_is_long(capsys):
    from multi_sessionizer.infrastructure.messages import ConsoleMessageOutput

    rows = [
        (
            "directory",
            "[external] /home/u/very/long/scikit_learn_data",
            "/home/u/very/long/scikit_learn_data",
        ),
        ("workspace", "[external] myws", "myws"),
    ]
    ConsoleMessageOutput().external_list(rows)
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert "  /home/u/very/long/scikit_learn_data" in out[0]
    assert out[0].endswith("scikit_learn_data")
    assert out[1].endswith("myws")
    assert "mywsmyws" not in "".join(out)
