from importlib.util import find_spec


def test_module_layout_smoke():
    assert find_spec("bangstats_server.app") is not None
    assert find_spec("bangstats_server.core.adapters.bestdori") is not None
    assert find_spec("bangstats_server.core.adapters.ocr.gemini") is not None
    assert find_spec("bangstats_server.core.services.scan") is not None
    assert find_spec("bangstats_server.core.services.song") is not None
