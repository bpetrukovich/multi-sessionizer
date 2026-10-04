"""App wiring tests with fake adapters (FR-020, US3/US4).

Injects fake adapters into ``FlowDeps`` and asserts the wiring sequence with no
real subprocess/filesystem/environment/terminal side effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from multi_sessionizer.app.configuration import Config, ConfigNotFoundError
from multi_sessionizer.app.flows import interactive_flow, run_selection, switch_flow
from multi_sessionizer.app.ports import FlowDeps
from multi_sessionizer.domain.models import Command, CommandPlan, RuntimeSnapshot, Selection


def cmd(program, *args):
    return Command(program, args)


class FakeConfigLoader:
    def __init__(self):
        self.calls: list[str] = []
        self.cfg = Config()
        self.missing = ([], [])
        self.not_found: ConfigNotFoundError | None = None

    def load(self) -> Config:
        self.calls.append("load")
        if self.not_found is not None:
            raise self.not_found
        return self.cfg

    def missing_files(self, cfg):
        self.calls.append("missing_files")
        return self.missing[0]

    def missing_dirs(self, cfg):
        self.calls.append("missing_dirs")
        return self.missing[1]


class FakeDiscovery:
    def __init__(self, dirs=(), files=()):
        self.calls: list[str] = []
        self.dirs = list(dirs)
        self.files = list(files)

    def collect_dirs(self, cfg):
        self.calls.append("collect_dirs")
        return self.dirs

    def collect_files(self, cfg):
        self.calls.append("collect_files")
        return self.files


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

    def classify_args(self, argv: Sequence[str]):
        self.calls.append("classify_args")
        return self.classified

    def classify_selection(self, lines: list[str]) -> Selection:
        self.calls.append("classify_selection")
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
        self.missing_files = []
        self.missing_dirs = []
        self.errors = []

    def config_not_found(self, path: object) -> None:
        self.calls.append("config_not_found")
        self.config_path = path

    def missing_paths(self, missing_files, missing_dirs) -> None:
        self.calls.append("missing_paths")
        self.missing_files = missing_files
        self.missing_dirs = missing_dirs

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
        discovery=FakeDiscovery(dirs=["/a/one"], files=["/f"]),
        scorer=FakeScorer("10.0 /a/one\n"),
        picker=FakePicker(selected=["/a/one"]),
        classifier=FakeClassifier(selection=Selection(("/a/one",), ())),
        probe=FakeProbe(snapshot=RuntimeSnapshot(False, False, {})),
        executor=FakeExecutor(),
    )
    assert interactive_flow(deps) == 0
    assert deps.config_loader.calls == ["load", "missing_files", "missing_dirs"]
    assert deps.discovery.calls == ["collect_dirs", "collect_files"]
    assert deps.scorer.calls == ["scores"]
    assert deps.picker.calls == ["pick"]
    assert deps.classifier.calls == ["classify_selection"]
    assert deps.probe.calls == ["snapshot"]
    assert deps.executor.calls == ["execute"]
    assert deps.executor.plans == [plan]
    assert deps.picker.items == ["/a/one", "/f"]


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


def test_missing_paths_returns_one():
    loader = FakeConfigLoader()
    loader.missing = (["/nofile"], ["/nodir"])
    messages = FakeMessages()
    deps = make_deps(config_loader=loader, messages=messages)
    assert interactive_flow(deps) == 1
    assert messages.calls == ["missing_paths"]
    assert messages.missing_files == ["/nofile"]
    assert messages.missing_dirs == ["/nodir"]


def test_empty_picker_selection_returns_zero_executor_not_called():
    deps = make_deps(picker=FakePicker(selected=[]), executor=FakeExecutor())
    assert interactive_flow(deps) == 0
    assert deps.executor.calls == []


def test_full_wiring_replaceable_executor(monkeypatch, tmp_path):
    from multi_sessionizer.infrastructure.classifier import PathSelectionClassifier
    from multi_sessionizer.infrastructure.config_loader import FileConfigLoader
    from multi_sessionizer.infrastructure.discovery import FileCandidateDiscovery

    project = tmp_path / "projects" / "one"
    project.mkdir(parents=True)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(f'additional_dirs = ["{project}"]\n')
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
