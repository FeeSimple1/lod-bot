def test_imports():
    import lod_ai
    assert hasattr(lod_ai, "__all__") or lod_ai.__name__ == "lod_ai"
