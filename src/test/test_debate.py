import pytest

from src.debate import Debate


def test_simple_debate() -> None:
    debate = Debate("simple_update")
    debate.init_new_debate(["A", "B"], [1.0, 2.0])
    debate.update([1.0, 2.0])
    assert debate.judge_winner() == "B"

    debate.update([1.0, 2.0])
    assert debate.judge_winner() == "B"

    debate.update([2.0, 1.0])
    assert debate.judge_winner() == "B"

    debate.update([10.0, 1.0])
    assert debate.judge_winner() == "A"


if __name__ == "__main__":
    pytest.main(["-v", "-s", "src/test/test_debate.py"])
