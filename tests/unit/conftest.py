import pytest

from factories import CONFIG_DIR
from vgcp.config import load_config
from vgcp.shield import VerificationShield


@pytest.fixture(scope="session")
def cfg():
    return load_config(CONFIG_DIR)


@pytest.fixture(scope="session")
def shield(cfg):
    return VerificationShield.from_config(cfg)
