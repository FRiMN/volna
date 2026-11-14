"""Tab and listing icons: friendly names for known folders, names for row glyphs."""

from pathlib import Path

from volna.naming import content_icon, content_icon_label, tab_icon, tab_title


def test_home_location_has_friendly_name_and_icon() -> None:
    home = Path.home()
    assert tab_title(home) == "Домашняя папка"
    assert tab_icon(home) == "home"


def test_downloads_folder_in_home_uses_download_icon() -> None:
    for name in ("Загрузки", "Downloads"):
        path = Path.home() / name
        assert tab_title(path) == name
        assert tab_icon(path) == "down"


def test_downloads_folder_elsewhere_is_an_ordinary_folder(tmp_path: Path) -> None:
    path = tmp_path / "Загрузки"
    assert tab_title(path) == "Загрузки"
    assert tab_icon(path) == "folder"


def test_nested_directory_uses_its_basename(tmp_path: Path) -> None:
    path = tmp_path / "projects" / "volna"
    assert tab_title(path) == "volna"
    assert tab_icon(path) == "folder"


def test_filesystem_root_is_named_by_its_path() -> None:
    assert tab_title(Path("/")) == "/"
    assert tab_icon(Path("/")) == "folder"


def test_listing_folders_use_the_saturated_glyph() -> None:
    assert content_icon(True) == "folder-filled"
    assert content_icon(False) == "file"


def test_listing_glyph_carries_an_accessible_name() -> None:
    assert content_icon_label(True) == "Папка"
    assert content_icon_label(False) == "Файл"
