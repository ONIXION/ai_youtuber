# python -m src.test.test_actions
import logging
from logging import Formatter, StreamHandler, getLogger

import py_trees
import pytest

from src.actions import SingleAgentAction
from src.agent import AiAgent, TalkFormat

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


def print_response_callback(response: str) -> None:
    message = TalkFormat.model_validate_json(response)
    print(f"AI callback: {message.reply}")
    print(f"AI callback: {message.emotion}")
    print(f"AI callback: {message.action}")


def test_single_agent_action() -> None:
    logger.info("test_single_agent_action start")

    logger.info("==========init==========")
    blackboard = py_trees.blackboard.Client(name="AgentDialog")
    blackboard.register_key(key="last_speaker", access=py_trees.common.Access.WRITE)
    blackboard.last_speaker = ""
    blackboard.register_key(key="agent1_response", access=py_trees.common.Access.WRITE)
    blackboard.agent1_response = ""
    agent = AiAgent(response_callback=print_response_callback)
    agent_dict = {"agent1": agent}
    action = SingleAgentAction("test_action", agent_dict)

    logger.info("==========call action==========")
    action.initialise()
    action.update()

    logger.info("==========assert==========")
    logger.info(f"last_speaker: {blackboard.last_speaker}")
    logger.info(f"agent1_response: {blackboard.agent1_response}")
    assert blackboard.last_speaker == "agent1"
    assert blackboard.agent1_response != ""


if __name__ == "__main__":
    pytest.main(["-v", "-s", "src/test/test_actions.py"])
