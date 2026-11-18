import agentproof


def test_package_has_version() -> None:
    assert isinstance(agentproof.__version__, str)
    assert agentproof.__version__ != ""
