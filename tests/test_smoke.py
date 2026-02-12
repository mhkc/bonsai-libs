def test_version_importable():
    import importlib

    pkg = importlib.import_module("api_client")
    assert hasattr(pkg, "__version__")
