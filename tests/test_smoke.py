from importlib.util import find_spec


def test_module_layout_smoke():
    assert find_spec("bangstats.cli.app") is not None
    assert find_spec("bangstats.adapters.bestdori") is not None
    assert find_spec("bangstats.adapters.ocr.gemini") is not None
    assert find_spec("bangstats.services.scanning.scan") is not None
    assert find_spec("bangstats.services.data.song") is not None
