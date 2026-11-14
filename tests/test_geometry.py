from volna.geometry import edge_at


def test_corners() -> None:
    width, height = 1440, 900
    assert edge_at(0, 0, width, height) == "nw"
    assert edge_at(width - 1, 0, width, height) == "ne"
    assert edge_at(0, height - 1, width, height) == "sw"
    assert edge_at(width - 1, height - 1, width, height) == "se"


def test_edges() -> None:
    width, height = 1440, 900
    assert edge_at(700, 2, width, height) == "n"
    assert edge_at(700, height - 2, width, height) == "s"
    assert edge_at(2, 450, width, height) == "w"
    assert edge_at(width - 2, 450, width, height) == "e"


def test_client_area_has_no_edge() -> None:
    width, height = 1440, 900
    assert edge_at(700, 450, width, height) is None
    assert edge_at(700, 20, width, height) is None


def test_out_of_bounds() -> None:
    width, height = 1440, 900
    assert edge_at(-1, 450, width, height) is None
    assert edge_at(width, 450, width, height) is None
    assert edge_at(700, height, width, height) is None
    assert edge_at(0, 0, 0, 0) is None
