"""窄屏格式化的形狀不變量。重點不是算得對，是寬度不會亂跳。"""

from __future__ import annotations

import pytest

from nvitiny.view.units import duration, mhz


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0:00:00"),
        (5, "0:00:05"),
        (725, "0:12:05"),
        (3600, "1:00:00"),
        (57167, "15:52:47"),
        (266465, "74:01:05"),        # 三天多，小時不進位成天
        (34560000, "9600:00:00"),
    ],
)
def test_duration_always_has_all_three_units(seconds, expected):
    """nvitop 的 running_time_human 有三種形狀，這裡一律時分秒。"""
    assert duration(seconds) == expected


def test_duration_missing_value_is_a_dash():
    assert duration(None) == "-"


@pytest.mark.parametrize("seconds", [0, 1, 59, 3599, 3600, 359999])
def test_duration_is_eight_cells_up_to_four_days(seconds):
    """99:59:59 以內不超過八格，proc_row 的欄寬照這個訂。"""
    assert len(duration(seconds).rjust(8)) == 8
    assert len(duration(seconds)) <= 8


@pytest.mark.parametrize(
    ("value", "limit", "compact", "expected"),
    [
        (2405, 3003, False, "2405/3003MHz"),
        (2405, None, False, "2405MHz"),     # 上限拿不到就不硬湊分母
        (2405, 3003, True, "2405MHz"),      # 窄屏把分母的位置讓給 bar
        (None, 3003, False, None),
    ],
)
def test_mhz_matches_the_watts_convention(value, limit, compact, expected):
    """跟 watts() 同一套規則，兩個欄位並排在同一列。"""
    assert mhz(value, limit, compact=compact) == expected
