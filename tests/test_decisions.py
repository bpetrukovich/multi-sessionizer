from multi_sessionizer.decisions import Command, plan


def cmd(program, *args):
    return Command(program, args)


def test_single_dir_attach():
    assert plan(
        ["/a/my.project"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing={},
    ) == [
        cmd("zoxide", "add", "/a/my.project"),
        cmd("tmux", "new-session", "-ds", "my_project", "-c", "/a/my.project"),
        cmd("tmux", "attach", "-t", "my_project"),
    ]


def test_single_dir_reuses_existing_session():
    assert plan(
        ["/a/my.project"],
        [],
        in_tmux=False,
        tmux_server_running=True,
        existing={"my_project": "/a/my.project"},
    ) == [
        cmd("zoxide", "add", "/a/my.project"),
        cmd("tmux", "attach", "-t", "my_project"),
    ]


def test_single_dir_in_tmux_switches():
    assert plan(
        ["/a/proj"],
        [],
        in_tmux=True,
        tmux_server_running=True,
        existing={},
    ) == [
        cmd("zoxide", "add", "/a/proj"),
        cmd("tmux", "new-session", "-ds", "proj", "-c", "/a/proj"),
        cmd("tmux", "switch-client", "-t", "proj"),
        cmd("tmux", "refresh-client", "-S"),
    ]


def test_multi_dirs_attach_first():
    assert plan(
        ["/a/one", "/b/two"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing={},
    ) == [
        cmd("zoxide", "add", "/a/one"),
        cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
        cmd("zoxide", "add", "/b/two"),
        cmd("tmux", "new-session", "-ds", "two", "-c", "/b/two"),
        cmd("tmux", "attach", "-t", "one"),
    ]


def test_multi_dirs_in_tmux_choose_session():
    cmds = plan(
        ["/a/one", "/b/two"],
        [],
        in_tmux=True,
        tmux_server_running=True,
        existing={},
    )
    assert cmds[-2:] == [
        cmd("tmux", "choose-session"),
        cmd("tmux", "refresh-client", "-S"),
    ]


def test_multi_dirs_server_running_plain_attach():
    cmds = plan(
        ["/a/one", "/b/two"],
        [],
        in_tmux=False,
        tmux_server_running=True,
        existing={},
    )
    assert cmds[-1] == cmd("tmux", "attach")


def test_duplicate_basenames_get_disambiguated():
    assert plan(
        ["/a/dup", "/b/dup"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing={},
    ) == [
        cmd("zoxide", "add", "/a/dup"),
        cmd("tmux", "new-session", "-ds", "dup", "-c", "/a/dup"),
        cmd("zoxide", "add", "/b/dup"),
        cmd("tmux", "new-session", "-ds", "dup-2", "-c", "/b/dup"),
        cmd("tmux", "attach", "-t", "dup"),
    ]


def test_existing_session_reused_when_same_path():
    assert plan(
        ["/a/dup"],
        [],
        in_tmux=False,
        tmux_server_running=True,
        existing={"dup": "/a/dup"},
    ) == [
        cmd("zoxide", "add", "/a/dup"),
        cmd("tmux", "attach", "-t", "dup"),
    ]


def test_existing_session_of_other_path_creates_disambiguated():
    assert plan(
        ["/b/dup"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing={"dup": "/a/dup"},
    ) == [
        cmd("zoxide", "add", "/b/dup"),
        cmd("tmux", "new-session", "-ds", "dup-2", "-c", "/b/dup"),
        cmd("tmux", "attach", "-t", "dup-2"),
    ]


def test_disambiguation_skips_taken_suffixes():
    assert plan(
        ["/d/dup"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing={"dup": "/a/dup", "dup-2": "/c/dup"},
    ) == [
        cmd("zoxide", "add", "/d/dup"),
        cmd("tmux", "new-session", "-ds", "dup-3", "-c", "/d/dup"),
        cmd("tmux", "attach", "-t", "dup-3"),
    ]


def test_existing_session_reused_after_suffixed_creation():
    assert plan(
        ["/b/dup"],
        [],
        in_tmux=False,
        tmux_server_running=True,
        existing={"dup": "/a/dup", "dup-2": "/b/dup"},
    ) == [
        cmd("zoxide", "add", "/b/dup"),
        cmd("tmux", "attach", "-t", "dup-2"),
    ]


def test_empty_plan():
    assert (
        plan(
            [],
            [],
            in_tmux=False,
            tmux_server_running=False,
            existing={},
        )
        == []
    )
