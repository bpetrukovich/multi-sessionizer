"""App wiring tests with fake adapters (FR-018/FR-020, US1/US3/US4).

Injects fake adapters into ``FlowDeps`` and asserts the wiring sequence with no
real subprocess/filesystem/environment/terminal side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from multi_sessionizer.app.configuration import Config, ConfigError, ConfigNotFoundError
from multi_sessionizer.app.flows import interactive_flow, run_selection, session_flow, switch_flow
from multi_sessionizer.app.ports import FlowDeps
from multi_sessionizer.domain.models import (
    Command,
    CommandPlan,
    RuntimeSnapshot,
    Selection,
    SessionEntry,
)
from multi_sessionizer.domain.workspace import fingerprint

WS_DEF = "session_name: myws\nwindows:\n  - shell_command: vim\n"
BAD_WS = "windows: []\n"


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


def make_deps(**kw):
    kw.setdefault("config_loader", FakeConfigLoader())
    kw.setdefault("discovery", FakeDiscovery())
    kw.setdefault("scorer", FakeScorer())
    kw.setdefault("picker", FakePicker())
    kw.setdefault("classifier", FakeClassifier())
    kw.setdefault("probe", FakeProbe())
    kw.setdefault("executor", FakeExecutor())
    kw.setdefault("messages", FakeMessages())
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
