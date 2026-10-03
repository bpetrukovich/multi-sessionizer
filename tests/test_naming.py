import pytest

from multi_sessionizer.naming import session_name


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/home/user/work/my.project", "my_project"),
        ("/home/user/work/project", "project"),
        ("/home/user/work/my.project.v2", "my_project_v2"),
        ("/home/user/work", "work"),
        ("/", "/"),
        ("/home/user/work/project/", "project"),
        ("/home/user/work/with space", "with space"),
    ],
)
def test_session_name(path, expected):
    assert session_name(path) == expected
