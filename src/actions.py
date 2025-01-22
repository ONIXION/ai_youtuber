import asyncio
import logging
import random
from abc import ABC, abstractmethod
from logging import Formatter, StreamHandler, getLogger

import py_trees
import py_trees.behaviours

from src.agent import AiAgent, TalkFormat, TalkInput

# ログの設定
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


class BaseAgentAction(py_trees.behaviour.Behaviour, ABC):
    def __init__(
        self,
        name: str,
        agent_dict: dict[str, AiAgent],
    ) -> None:
        super(BaseAgentAction, self).__init__(name)
        self.agent_dict = agent_dict
        self.blackboard = self.attach_blackboard_client()
        for key in agent_dict.keys():
            self.blackboard.register_key(
                key=f"{key}_response", access=py_trees.common.Access.WRITE
            )
        self.blackboard.register_key(
            key="last_speaker", access=py_trees.common.Access.WRITE
        )
        logger.info(f"AgentAction: {name} を初期化しました")

    def allocate_agent(self) -> str:
        """agent_dictから話者を選択する
        前回の話者がいる場合は前回の話者以外のエージェントをランダムに選択する
        前回の話者がいない場合はランダムに選択する
        エージェントが1つしかない場合はそのエージェントを選択する

        Returns:
            str: agent_dictのキー
        """
        if not self.blackboard.last_speaker or self.blackboard.last_speaker == "":
            return random.choice(list(self.agent_dict.keys()))
        elif len(self.agent_dict) == 1:
            return list(self.agent_dict.keys())[0]
        else:
            # 前回の話者以外のエージェントを選択
            agent_list = list(self.agent_dict.keys())
            assert (
                self.blackboard.last_speaker in agent_list
            ), f"{self.blackboard.last_speaker} is not in {agent_list}"
            agent_list.remove(self.blackboard.last_speaker)
            return random.choice(agent_list)

    def initialise(self) -> None:
        pass

    def update(self) -> py_trees.common.Status:
        try:
            agent_key = self.allocate_agent()
            agent = self.agent_dict[agent_key]
            prompt = self.generate_prompt()
            logger.debug(f"AgentAction: {agent_key} に対しての入力: {prompt}")

            agent_input = TalkInput(name="host", input=prompt).model_dump_json()
            response = asyncio.get_event_loop().run_until_complete(
                agent.graph.ainvoke({"messages": [agent_input]})
            )
            message = TalkFormat.model_validate_json(
                response["messages"][-1].content
            ).reply
            setattr(self.blackboard, f"{agent_key}_response", message)
            self.blackboard.last_speaker = agent_key
        except Exception as e:
            raise e

        return py_trees.common.Status.SUCCESS

    @abstractmethod
    def generate_prompt(self) -> str:
        pass


class SingleAgentAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        # ユーザーからの入力を受け取る
        prompt = input("ユーザーからの入力を入力してください: ")
        return prompt
