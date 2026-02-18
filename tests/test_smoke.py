def test_version_importable():
    import importlib

    pkg = importlib.import_module("bonsai_libs")
    assert hasattr(pkg, "__version__")
