from bangstats_server.core.utils.chart_meta import chart_level_for_difficulty


def test_chart_level_scalar():
    assert chart_level_for_difficulty({"expert": 26}, "expert") == 26
    assert chart_level_for_difficulty({"Expert": 27}, "expert") == 27


def test_chart_level_list():
    assert chart_level_for_difficulty({"special": [28, 29]}, "special") == 28


def test_chart_level_missing():
    assert chart_level_for_difficulty({}, "expert") is None
    assert chart_level_for_difficulty({"expert": 26}, "hard") is None
