from __future__ import annotations

import pytest

from nvitiny.app.demo import synth_history
from nvitiny.core.sample import from_fixture

FIXTURE_NAMES = ("gb10", "dual")

# scope="module"：多個測試吃同一張畫面，function scope 會重複渲染六次。
# 前提是只讀 —— 要改動拿到的畫面得先 copy。


@pytest.fixture(scope="module", params=FIXTURE_NAMES)
def snapshot(request):
    return from_fixture(request.param)


@pytest.fixture(scope="module")
def histories(snapshot):
    return {gpu.index: synth_history(gpu.index * 1.7) for gpu in snapshot.gpus}
