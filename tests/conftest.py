from __future__ import annotations

import pytest

from nvitiny.app.demo import synth_history
from nvitiny.core.sample import from_fixture

FIXTURE_NAMES = ("gb10", "dual")


@pytest.fixture(params=FIXTURE_NAMES)
def snapshot(request):
    return from_fixture(request.param)


@pytest.fixture
def histories(snapshot):
    return {gpu.index: synth_history(gpu.index * 1.7) for gpu in snapshot.gpus}
