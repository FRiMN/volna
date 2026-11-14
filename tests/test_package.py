def test_package_importable() -> None:
    import volna

    assert volna.__name__ == "volna"
