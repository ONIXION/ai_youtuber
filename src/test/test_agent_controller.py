# python -m src.test.test_agent_controller

import logging
from collections import deque
from logging import Formatter, StreamHandler, getLogger
from typing import Callable

import pytest

from src.agent import TalkFormat
from src.agent_controller import DualAgentController

if __name__ == "__main__":
    logger = getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler = StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(handler_format)
    logger.addHandler(stream_handler)
else:
    logger = getLogger("__main__")
    logger.setLevel(logging.DEBUG)


def response_callback_creater(name: str) -> Callable[[str], None]:
    def print_response_callback(response: str) -> None:
        message = TalkFormat.model_validate_json(response)
        print(f"AI callback: {message.reply}")
        print(f"AI callback: {message.emotion}")
        print(f"AI callback: {message.action}")

    return print_response_callback


def conversation_agenda_callback() -> str:
    return "りんごは蜜柑より甘い"


def debate_agenda_callback() -> list[str]:
    return ["りんごは蜜柑より甘い", "蜜柑はりんごより甘い"]


def waiting_callback() -> bool:
    return True


def fetch_comment_callback_creater() -> Callable[[], str]:
    comment_queue: deque = deque(maxlen=10)
    comment_queue.append("りんごは蜜柑より甘い")
    comment_queue.append("蜜柑はりんごより甘い")
    comment_queue.append("りんごは蜜柑よりはるかに甘い")
    comment_queue.append("蜜柑はりんごよりはるかに甘い")
    comment_queue.append("りんごは蜜柑よりやや甘い")
    comment_queue.append("蜜柑はりんごよりやや甘い")

    def fetch_comment_callback() -> str:
        res = comment_queue.popleft()
        assert isinstance(res, str)
        return res

    return fetch_comment_callback


def test_DualAgentController() -> None:
    logger.info("==========init==========")

    name_list = ["雲霧星奈", "星霧月音"]
    port_list = [9222, 9223]

    num_update_comment = 1

    agent_controller = DualAgentController(
        name_list=name_list,
        port_list=port_list,
        response_callback_creater=response_callback_creater,
        conversation_agenda_callback=conversation_agenda_callback,
        debate_agenda_callback=debate_agenda_callback,
        waiting_callback=waiting_callback,
        fetch_comment_callback=fetch_comment_callback_creater(),
        num_update_comment=num_update_comment,
    )

    logger.info("==========test==========")
    agent_controller.start_dialog()

    logger.info("==========assert==========")
    assert agent_controller.blackboard.last_speaker != ""
    assert agent_controller.blackboard.agent1_response != ""
    assert agent_controller.blackboard.agent2_response != ""


if __name__ == "__main__":
    test_DualAgentController()
    # pytest.main(["-v", "-s", "src/test/test_agent_controller.py"])
