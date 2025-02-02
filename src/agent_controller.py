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
                    "PickAgendaAction", self.agent_dict, conversation_agenda_callback
                ),
                WaitingAction("WaitingAction1", waiting_callback),
                ConversationAction("ConversationAction1", self.agent_dict),
                WaitingAction("WaitingAction1", waiting_callback),
                ConversationAction("ConversationAction2", self.agent_dict),
                WaitingAction("WaitingAction1", waiting_callback),
                ConversationAction("ConversationAction3", self.agent_dict),
                WaitingAction("WaitingAction1", waiting_callback),
                PrepareDebateAction(
                    "PrepareDebateAction",
                    self.agent_dict,
                    debate_agenda_callback,
                    self.debate,
                    mode="Think",
                ),
                WaitingAction("WaitingAction1", waiting_callback),
                StartDebateAction("StartDebateAction", self.agent_dict),
                UpdateAction(
                    "UpdateAction1",
                    self.debate,
                    fetch_comment_callback,
                    num_update_comment,
                ),
                WaitingAction("WaitingAction1", waiting_callback),
                DebateAction("DebateAction1", self.agent_dict),
                UpdateAction(
                    "UpdateAction1",
                    self.debate,
                    fetch_comment_callback,
                    num_update_comment,
                ),
                WaitingAction("WaitingAction1", waiting_callback),
                DebateAction("DebateAction2", self.agent_dict),
                UpdateAction(
                    "UpdateAction1",
                    self.debate,
                    fetch_comment_callback,
                    num_update_comment,
                ),
                WaitingAction("WaitingAction1", waiting_callback),
                EndDebateAction("EndDebateAction", self.agent_dict, self.debate),
                WaitingAction("WaitingAction1", waiting_callback),
                PlayAgainAction("PlayAgainAction"),
            ]
        )

    def __del__(self) -> None:
        """デコンストラクタ"""
        self.procA.terminate()
        self.procB.terminate()
        self.embedding_engine.close()
        del self.embedding_engine
        del self.debate

    def start_dialog(self) -> None:
        while True:
            self.root.tick_once()
            # PlayAgain ノードの結果によってループを継続するか決定
            play_again_status = self.blackboard.play_again_status
            if play_again_status == py_trees.common.Status.FAILURE:
                break
