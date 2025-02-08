# python -m src.test.test_debate

import logging
from logging import Formatter, StreamHandler, getLogger

import pytest

from src.utils.debate import Debate
from src.utils.embedding import EmbeddinEngine

# ログの設定
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(handler_format)
logger.addHandler(stream_handler)


# def test_simple_debate() -> None:
#     debate = Debate("simple_update")
#     debate.init_new_debate(["A", "B"], [1.0, 2.0])
#     debate.update([1.0, 2.0])
#     assert debate.judge_winner() == "B"

#     debate.update([1.0, 2.0])
#     assert debate.judge_winner() == "B"

#     debate.update([2.0, 1.0])
#     assert debate.judge_winner() == "B"

#     debate.update([10.0, 1.0])
#     assert debate.judge_winner() == "A"


def test_embedding_based_debate() -> None:
    embedding = EmbeddinEngine()
    debate = Debate("embedding_based_update", embedding)
    debate.init_new_debate(["A", "B"], ["りんごは蜜柑より甘い", "蜜柑はりんごより甘い"])
    debate.update("パイナップルは蜜柑より甘い")
    debate.update("バナナはりんごより甘い")
    debate.update("蜜柑はどんな果物よりも甘い")
    debate.update("りんごは甘くない")
    winner = debate.judge_winner()

    logger.info(f"winner: {winner}")
    assert winner == "B" or winner == "A"


if __name__ == "__main__":
    pytest.main(["-v", "-s", "src/test/test_debate.py"])
