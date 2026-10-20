import os

import pytest
from hypothesis import settings

from factories import CONFIG_DIR

# Property tests are reproducible by default (audit L4): the same examples on every
# run and no example database. HYPOTHESIS_PROFILE=explore searches randomly instead.
settings.register_profile("deterministic", derandomize=True, database=None)
settings.register_profile("explore", derandomize=False)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "deterministic"))
from vgcp.config import load_config
from vgcp.shield import VerificationShield


@pytest.fixture(scope="session")
def cfg():
    return load_config(CONFIG_DIR)


@pytest.fixture(scope="session")
def shield(cfg):
    return VerificationShield.from_config(cfg)
