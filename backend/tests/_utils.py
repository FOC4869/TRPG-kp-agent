"""测试辅助：假随机源。"""


class FakeRng:
    """按给定序列返回 randint 结果的假随机源，用于确定性测试。"""

    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def randint(self, a, b):
        if self._i >= len(self._values):
            raise AssertionError("FakeRng 取值耗尽")
        v = self._values[self._i]
        self._i += 1
        assert a <= v <= b, f"FakeRng 值 {v} 超出 [{a},{b}]"
        return v
