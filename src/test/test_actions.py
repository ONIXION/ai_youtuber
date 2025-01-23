# python -m src.test.test_actions
import logging
from logging import Formatter, StreamHandler, getLogger

import py_trees
import pytest

from src.agent import AiAgent, TalkFormat
from src.prompt_define import agent1_talk_prompt_txt, agent2_talk_prompt_txt
from src.utils.actions import (
    ConversationAction,
    PickAgendaAction,
    PrepareDebateAction,
    SingleAgentAction,
)

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


# def test_single_agent_action() -> None:
#     logger.info("test_single_agent_action start")

#     logger.info("==========init==========")
#     blackboard = py_trees.blackboard.Client(name="AgentDialog")
#     blackboard.register_key(key="last_speaker", access=py_trees.common.Access.WRITE)
#     blackboard.last_speaker = ""
#     blackboard.register_key(key="agent1_response", access=py_trees.common.Access.WRITE)
#     blackboard.agent1_response = ""
#     agent = AiAgent(
#         system_prompt=agent2_talk_prompt_txt, response_callback=print_response_callback
#     )
#     agent_dict = {"agent1": agent}
#     action = SingleAgentAction("test_action", agent_dict)

#     logger.info("==========call action==========")
#     action.initialise()
#     action.update()

#     logger.info("==========assert==========")
#     logger.info(f"last_speaker: {blackboard.last_speaker}")
#     logger.info(f"agent1_response: {blackboard.agent1_response}")
#     assert blackboard.last_speaker == "agent1"
#     assert blackboard.agent1_response != ""


# def test_conversation() -> None:
#     logger.info("test_conversation start")
#     logger.info("==========init==========")
#     blackboard = py_trees.blackboard.Client(name="AgentDialog")
#     blackboard.register_key(key="last_speaker", access=py_trees.common.Access.WRITE)
#     blackboard.last_speaker = ""
#     blackboard.register_key(key="agent1_response", access=py_trees.common.Access.WRITE)
#     blackboard.agent1_response = ""

#     agent1 = AiAgent(
#         system_prompt=agent1_talk_prompt_txt, response_callback=print_response_callback
#     )
#     agent2 = AiAgent(
#         system_prompt=agent2_talk_prompt_txt, response_callback=print_response_callback
#     )
#     agent_dict = {"agent1": agent1, "agent2": agent2}
#     root = py_trees.composites.Sequence("root", memory=False)

#     def callback() -> str:
#         prompt = input("ユーザーからの入力を入力してください: ")
#         return prompt

#     root.add_children(
#         [
#             PickAgendaAction("PickAgendaAction", agent_dict, callback),
#             ConversationAction("ConversationAction1", agent_dict),
#             ConversationAction("ConversationAction2", agent_dict),
#         ]
#     )

#     logger.info("==========call action==========")
#     root.tick_once()

#     logger.info("==========assert==========")
#     logger.info(f"last_speaker: {blackboard.last_speaker}")
#     logger.info(f"agent1_response: {blackboard.agent1_response}")
#     assert blackboard.last_speaker == "agent2" or blackboard.last_speaker == "agent1"
#     assert blackboard.agent1_response != "" and blackboard.agent1_response != ""


def test_prepare_debate() -> None:
    logger.info("test_prepare_debate start")
    logger.info("==========init==========")
    blackboard = py_trees.blackboard.Client(name="AgentDialog")
    blackboard.register_key(key="last_speaker", access=py_trees.common.Access.WRITE)
    blackboard.last_speaker = ""
    blackboard.register_key(key="agent1_response", access=py_trees.common.Access.WRITE)
    blackboard.agent1_response = ""
    blackboard.register_key(key="agent2_response", access=py_trees.common.Access.WRITE)
    blackboard.agent2_response = ""

    agent1 = AiAgent(
        system_prompt=agent1_talk_prompt_txt, response_callback=print_response_callback
    )
    agent2 = AiAgent(
        system_prompt=agent2_talk_prompt_txt, response_callback=print_response_callback
    )
    agent_dict = {"agent1": agent1, "agent2": agent2}

    def callback() -> list[str]:
        return ["りんごは蜜柑より甘い", "蜜柑はりんごより甘い"]

    action = PrepareDebateAction("PickAgendaAction", agent_dict, callback)

    logger.info("==========call action==========")
    action.initialise()
    action.update()

    logger.info("==========assert==========")
    response1 = blackboard.agent1_response
    response2 = blackboard.agent2_response
    logger.info(f"agent1_response: {response1}")
    logger.info(f"agent2_response: {response2}")
    assert response1 != "" and response2 != ""


if __name__ == "__main__":
    # test_prepare_debate()
    pytest.main(["-v", "-s", "src/test/test_actions.py"])
