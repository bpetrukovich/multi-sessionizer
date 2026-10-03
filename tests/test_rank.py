from multi_sessionizer.rank import build_picker_list, parse_zoxide_scores, rank_dirs


def test_parse_scores_with_leading_space_and_path_spaces():
    text = " 420.0 /a/b\n  12.5 /c d/e\n0 /z\n"
    assert parse_zoxide_scores(text) == {
        "/a/b": 420.0,
        "/c d/e": 12.5,
        "/z": 0.0,
    }


def test_parse_line_without_score_is_defensive():
    assert parse_zoxide_scores("/path/only\n") == {"/path/only": 0.0}


def test_parse_empty():
    assert parse_zoxide_scores("") == {}


def test_rank_desc_stable():
    dirs = ["/a", "/b", "/c", "/d"]
    scores = {"/b": 5.0, "/d": 9.0, "/c": 5.0}
    assert rank_dirs(dirs, scores) == ["/d", "/b", "/c", "/a"]


def test_rank_all_zero_keeps_order():
    dirs = ["/a", "/b", "/c"]
    assert rank_dirs(dirs, {}) == ["/a", "/b", "/c"]


def test_build_picker_list_files_appended():
    dirs = ["/a", "/b"]
    scores = {"/b": 3.0}
    files = ["/f1", "/f2"]
    assert build_picker_list(dirs, scores, files) == ["/b", "/a", "/f1", "/f2"]
