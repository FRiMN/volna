from volna.views.format import format_date, format_size


def test_format_size() -> None:
    assert format_size(None) == "—"
    assert format_size(0) == "0 Б"
    assert format_size(512) == "512 Б"
    assert format_size(1024) == "1,0 КиБ"
    assert format_size(1536) == "1,5 КиБ"
    assert format_size(1024 * 1024) == "1,0 МиБ"


def test_format_date() -> None:
    assert format_date(None) == "—"
    assert format_date(0.0).count(".") == 2
