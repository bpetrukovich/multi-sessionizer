from multi_sessionizer.decisions import Command, plan


def cmd(program, *args):
    return Command(program, args)


def test_single_dir_attach():
    assert plan(
        ["/a/my.project"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
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
        existing=("my_project",),
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
        existing=(),
    ) == [
        cmd("zoxide", "add", "/a/proj"),
        cmd("tmux", "new-session", "-ds", "proj", "-c", "/a/proj"),
        cmd("tmux", "switch-client", "-t", "proj"),
        cmd("tmux", "refresh-client", "-S"),
    ]


def test_single_file_opens_nvim():
    assert plan(
        [],
        ["/a/b/file.py"],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
    ) == [
        cmd("zoxide", "add", "/a/b"),
        cmd("tmux", "new-session", "-ds", "b", "-c", "/a/b"),
        cmd("tmux", "send-keys", "-t", "b", "nvim '/a/b/file.py'", "Enter"),
        cmd("tmux", "attach", "-t", "b"),
    ]


def test_multi_dirs_attach_first():
    assert plan(
        ["/a/one", "/b/two"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
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
        existing=(),
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
        existing=(),
    )
    assert cmds[-1] == cmd("tmux", "attach")


def test_duplicate_basenames_reuse_session():
    assert plan(
        ["/a/dup", "/b/dup"],
        [],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
    ) == [
        cmd("zoxide", "add", "/a/dup"),
        cmd("tmux", "new-session", "-ds", "dup", "-c", "/a/dup"),
        cmd("zoxide", "add", "/b/dup"),
        cmd("tmux", "attach", "-t", "dup"),
    ]


def test_mixed_dirs_then_files_processed_in_order():
    assert plan(
        ["/a/one"],
        ["/b/two/file.py"],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
    ) == [
        cmd("zoxide", "add", "/a/one"),
        cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
        cmd("zoxide", "add", "/b/two"),
        cmd("tmux", "new-session", "-ds", "two", "-c", "/b/two"),
        cmd("tmux", "send-keys", "-t", "two", "nvim '/b/two/file.py'", "Enter"),
        cmd("tmux", "attach", "-t", "one"),
    ]


def test_multi_files_first_session_from_dirname():
    cmds = plan(
        [],
        ["/a/one/x.py", "/b/two/y.py"],
        in_tmux=False,
        tmux_server_running=False,
        existing=(),
    )
    assert cmds[-1] == cmd("tmux", "attach", "-t", "one")


def test_empty_plan():
    assert (
        plan(
            [],
            [],
            in_tmux=False,
            tmux_server_running=False,
            existing=(),
        )
        == []
    )
