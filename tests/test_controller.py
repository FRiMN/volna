import queue

from volna.controller import DirectoryController
from volna.core import DirModel, ScanState


def test_controller_feeds_model(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    model = DirModel()
    pending = queue.Queue()
    controller = DirectoryController(
        model, dispatch=lambda fn, *args: pending.put((fn, args))
    )

    controller.open(str(tmp_path))
    controller.join(5.0)
    _drain(pending)

    assert model.state is ScanState.READY
    assert {entry.name for entry in model.entries()} == {"a.txt", "sub"}
    controller.close()


def test_controller_reports_scan_error(tmp_path) -> None:
    model = DirModel()
    pending = queue.Queue()
    controller = DirectoryController(
        model, dispatch=lambda fn, *args: pending.put((fn, args))
    )

    controller.open(str(tmp_path / "missing"))
    controller.join(5.0)
    _drain(pending)

    assert model.state is ScanState.ERROR
    controller.close()


def _drain(pending: queue.Queue) -> None:
    while not pending.empty():
        callback, args = pending.get_nowait()
        callback(*args)
