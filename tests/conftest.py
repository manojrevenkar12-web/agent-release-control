import pytest

from arc.config import MODELS


@pytest.fixture(scope="session")
def trained() -> None:
    """The understanding tiers and the learned judge; trained once (about a minute) if missing."""
    if not (MODELS / "nlu.joblib").exists() or not (MODELS / "judge.joblib").exists():
        from arc.train import train

        train()


@pytest.fixture(scope="session")
def platform(trained):
    from arc.platform import SimPlatform

    return SimPlatform()
