import pytest


@pytest.fixture(autouse=True, scope="session")
def temporary_database(tmp_path_factory):
    """Every test talks to a throwaway database, never to backend/data/vitalis.db."""
    mp = pytest.MonkeyPatch()
    mp.setenv("VITALIS_DB", str(tmp_path_factory.mktemp("db") / "test.db"))
    yield
    mp.undo()
