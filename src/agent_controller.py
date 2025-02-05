import asyncio
import logging
import time
from logging import Formatter, StreamHandler, getLogger
from typing import Callable

import py_trees

from src.agent import AiAgent, think, web_search_creater
from src.prompt_define import agent1_talk_prompt_txt, agent2_talk_prompt_txt
from src.utils.actions import (
    ConversationAction,
    DebateAction,
    EndDebateAction,
    PickAgendaAction,
    PlayAgainAction,
    PrepareDebateAction,
    StartDebateAction,
    UpdateAction,
    WaitingAction,
)
from src.utils.browser_util import start_chrome
from src.utils.debate import Debate
from src.utils.embedding import EmbeddinEngine

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


class DualAgentController:
    def __init__(
        self,
        name_list: list[str],
        port_list: list[int],
        response_callback_creater: Callable[[str], Callable[[str], None]],
        conversation_agenda_callback: Callable,
        debate_agenda_callback: Callable,
        waiting_callback: Callable,
        fetch_comment_callback: Callable,
        scene_transition_callback: Callable,
        num_update_comment: int,
    ) -> None:
        logger.info("==========init Agent==========")
        self.blackboard = py_trees.blackboard.Client(name="AgentDialog")
        self.blackboard.register_key(
            key="last_speaker", access=py_trees.common.Access.WRITE
        )
        self.blackboard.last_speaker = ""
        self.blackboard.register_key(
            key="agent1_response", access=py_trees.common.Access.WRITE
        )
        self.blackboard.agent1_response = ""
        self.blackboard.register_key(
            key="agent2_response", access=py_trees.common.Access.WRITE
        )
        self.blackboard.agent2_response = ""
        self.blackboard.register_key(
            key="play_again_status", access=py_trees.common.Access.WRITE
        )
        self.blackboard.play_again_status = py_trees.common.Status.SUCCESS

        # portA = 9222
        # portB = 9223
        self.port_list = port_list

        self.procA = start_chrome(self.port_list[0], "C:/temp/chrome_profile_A")
        self.procB = start_chrome(self.port_list[1], "C:/temp/chrome_profile_B")

        self.agent1 = AiAgent(
            # "雲霧星奈",
            name=name_list[0],
            system_prompt=agent1_talk_prompt_txt,
            response_callback=response_callback_creater(name_list[0]),
            tool_list=[think, web_search_creater(self.port_list[0])],
        )
        self.agent2 = AiAgent(
            # "星霧月音",
            name=name_list[1],
            system_prompt=agent2_talk_prompt_txt,
            response_callback=response_callback_creater(name_list[1]),
            tool_list=[think, web_search_creater(self.port_list[1])],
        )
        self.agent_dict = {"agent1": self.agent1, "agent2": self.agent2}

        self.embedding_engine = EmbeddinEngine()
        self.debate = Debate("embedding_based_update", self.embedding_engine)

        time.sleep(3)

        self.root = py_trees.composites.Sequence("root", memory=False)
        self.root.add_children(
            [
                PickAgendaAction(
                    name="PickAgendaAction",
                    agent_dict=self.agent_dict,
                    fetch_comment_callback=conversation_agenda_callback,
                    scene_transition_callback=scene_transition_callback,
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                ConversationAction(
                    name="ConversationAction1", agent_dict=self.agent_dict
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                ConversationAction(
                    name="ConversationAction2", agent_dict=self.agent_dict
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                ConversationAction(
                    name="ConversationAction3", agent_dict=self.agent_dict
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                PrepareDebateAction(
                    name="PrepareDebateAction",
                    agent_dict=self.agent_dict,
                    create_agenda_callback=debate_agenda_callback,
                    debate=self.debate,
                    scene_transition_callback=scene_transition_callback,
                    mode="WebSearch",
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                StartDebateAction(name="StartDebateAction", agent_dict=self.agent_dict),
                UpdateAction(
                    name="UpdateAction1",
                    debate=self.debate,
                    fetch_comment_callback=fetch_comment_callback,
                    num_get_comment=num_update_comment,
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                DebateAction(name="DebateAction1", agent_dict=self.agent_dict),
                UpdateAction(
                    name="UpdateAction1",
                    debate=self.debate,
                    fetch_comment_callback=fetch_comment_callback,
                    num_get_comment=num_update_comment,
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                DebateAction(name="DebateAction2", agent_dict=self.agent_dict),
                UpdateAction(
                    name="UpdateAction1",
                    debate=self.debate,
                    fetch_comment_callback=fetch_comment_callback,
                    num_get_comment=num_update_comment,
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                EndDebateAction(
                    name="EndDebateAction",
                    agent_dict=self.agent_dict,
                    debate=self.debate,
                ),
                WaitingAction(name="WaitingAction1", waiting_callback=waiting_callback),
                PlayAgainAction(name="PlayAgainAction"),
            ]
        )

    def __del__(self) -> None:
        """デコンストラクタ"""
        self.procA.terminate()
        self.procB.terminate()
        self.embedding_engine.close()
        del self.embedding_engine
        del self.debate
        del self.agent1
        del self.agent2

    def start_dialog(self) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        while True:
            self.root.tick_once()
            # PlayAgain ノードの結果によってループを継続するか決定
            play_again_status = self.blackboard.play_again_status
            if play_again_status == py_trees.common.Status.FAILURE:
                break
