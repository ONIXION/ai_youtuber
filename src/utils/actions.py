import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from logging import Formatter, StreamHandler, getLogger
from typing import Callable

import py_trees
import py_trees.behaviours

from src.agent import AiAgent, TalkFormat, TalkInput
from src.utils.debate import Debate

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
    def generate_prompt(self) -> str | list[str]:
        pass


class BaseMultiAgentAction(BaseAgentAction, ABC):
    def update(self) -> py_trees.common.Status:
        try:
            prompt1, prompt2 = self.generate_prompt()
            agent1, agent2 = self.agent_dict.values()
            agent1_key, agent2_key = self.agent_dict.keys()

            logger.debug(f"AgentAction: {agent1_key} に対しての入力: {prompt1}")
            agent1_input = TalkInput(name="host", input=prompt1).model_dump_json()
            logger.debug(f"AgentAction: {agent2_key} に対しての入力: {prompt2}")
            agent2_input = TalkInput(name="host", input=prompt2).model_dump_json()

            # 全ての応答を得るまで待機
            responses = asyncio.get_event_loop().run_until_complete(
                asyncio.gather(
                    agent1.graph.ainvoke({"messages": [agent1_input]}),
                    agent2.graph.ainvoke({"messages": [agent2_input]}),
                )
            )
            response1, response2 = responses

            message1 = TalkFormat.model_validate_json(
                response1["messages"][-1].content
            ).reply
            message2 = TalkFormat.model_validate_json(
                response2["messages"][-1].content
            ).reply

            setattr(self.blackboard, f"{agent1_key}_response", message1)
            setattr(self.blackboard, f"{agent2_key}_response", message2)
        except Exception as e:
            raise e

        logger.debug(f"AgentAction: {agent1_key} の応答: {message1}")
        logger.debug(f"AgentAction: {agent2_key} の応答: {message2}")
        assert response1 is not None
        assert response2 is not None

        return py_trees.common.Status.SUCCESS

    @abstractmethod
    def generate_prompt(self) -> list[str]:
        pass


class SingleAgentAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        # ユーザーからの入力を受け取る
        prompt = input("ユーザーからの入力を入力してください: ")
        return prompt


class PickAgendaAction(BaseAgentAction):
    def __init__(
        self,
        name: str,
        agent_dict: dict[str, AiAgent],
        fetch_comment_callback: Callable,
    ) -> None:
        super().__init__(name, agent_dict)
        self.loader = fetch_comment_callback

    def generate_prompt(self) -> str:
        comment = self.loader()
        assert isinstance(comment, str)
        prompt_prefix = (
            "視聴者から以下の会話のアジェンダが送られてきました。これを読み上げた上で、アジェンダに対してあなたの意見を述べ、もう一方の出演者に対しても意見を促して下さい:\n",
            "アジェンダ：",
        )
        prompt = "\n".join(prompt_prefix) + comment
        return prompt


class ConversationAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        # last_speakerが空でないことを確認
        assert self.blackboard.last_speaker != "", "last_speaker is empty"

        # 前回の話者の発言を取得
        last_speaker = self.blackboard.last_speaker
        last_speaker_response = getattr(self.blackboard, f"{last_speaker}_response")
        assert isinstance(last_speaker_response, str)
        assert last_speaker_response != "", f"{last_speaker}_response is empty"

        prompt_prefix = (
            "あなたの相方から以下の発言がありました。これに対してあなたの意見を述べてください:\n",
            "相方の発言：",
        )
        prompt = "\n".join(prompt_prefix) + last_speaker_response
        return prompt


# TODO: エラーメッセージが正しく表示されるように修正
class PrepareDebateAction(BaseMultiAgentAction):
    def __init__(
        self,
        name: str,
        agent_dict: dict[str, AiAgent],
        create_agenda_callback: Callable,
        debate: Debate,
        mode: str = "WebSearch",
    ) -> None:
        super().__init__(name, agent_dict)
        self.loader = create_agenda_callback
        self.agenda: list[str] = []
        self.debate = debate
        self.mode = mode

    def start_new_debate(self) -> None:
        self.agenda = self.loader()
        assert isinstance(self.agenda, list), "agendaはlist型である必要があります"
        assert len(self.agenda) == 2, "agendaの長さは2である必要があります"
        assert all(
            [isinstance(item, str) for item in self.agenda]
        ), "agendaはstr型のリストである必要があります"

        self.debate.init_new_debate(
            names=list(self.agent_dict.keys()), arguments=self.agenda
        )

    def generate_prompt(self) -> list[str]:
        self.start_new_debate()

        if self.mode == "WebSearch":
            prompt_prefix = (
                "これから相方とディベートを行ってもらいます。あなたは以下の主張を正当化し、相方を論破してください。",
                "最初にシンキングタイムが与えられますので、あなたの主張を裏付ける根拠を調べて、準備してください。:\n",
                "WebSearchを使用し、Thinkは使用しないでください\n",
                "主張：",
            )
        elif self.mode == "Think":
            prompt_prefix = (
                "これから相方とディベートを行ってもらいます。あなたは以下の主張を正当化し、相方を論破してください。",
                "最初にシンキングタイムが与えられますので、あなたの主張を裏付ける根拠を考えて、準備してください。:\n",
                "Thinkを使用し、WebSearchは使用しないでください\n",
                "主張：",
            )
        else:
            raise ValueError("modeは'WebSearch'または'Think'である必要があります")
        prompt1 = "\n".join(prompt_prefix) + self.agenda[0]
        prompt2 = "\n".join(prompt_prefix) + self.agenda[1]
        return [prompt1, prompt2]


class StartDebateAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        prompt = (
            "シンキングタイムが終了しました。ディベートを開始します。最初に、あなたの論証を相方に対して述べてください。"
            "シンキングタイムで有効な情報が得られなかった場合は、自分の考えで論証を構築してください"
        )

        return prompt

    def allocate_agent(self) -> str:
        logger.debug("StartDebateAction: ランダムにエージェントを選択します")
        return random.choice(list(self.agent_dict.keys()))


class DebateAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        # last_speakerが空でないことを確認
        assert self.blackboard.last_speaker != "", "last_speaker is empty"

        # 前回の話者の発言を取得
        last_speaker = self.blackboard.last_speaker
        last_speaker_response = getattr(self.blackboard, f"{last_speaker}_response")
        assert isinstance(last_speaker_response, str)
        assert last_speaker_response != "", f"{last_speaker}_response is empty"

        prompt_prefix = (
            "あなたの相方は以下のように発言しました。これに対してシンキングタイムで考えた内容をもとに、反論してください:\n",
            "相方の発言：",
        )
        prompt = "\n".join(prompt_prefix) + last_speaker_response
        return prompt


class EndDebateAction(BaseMultiAgentAction):
    def __init__(
        self,
        name: str,
        agent_dict: dict[str, AiAgent],
        debate: Debate,
    ) -> None:
        super().__init__(name, agent_dict)
        self.debate = debate

    def generate_prompt(self) -> list[str]:
        winner = self.debate.judge_winner()

        prompt = (
            "ディベートが終了しました。結果を発表します。\n"
            "今回のディベートはとても盛り上がりました。どちらが勝ってもお互いを尊重し合いましょう。\n"
            f"勝者は{self.agent_dict[winner].name}です。おめでとうございます！"
        )

        return [prompt, prompt]


class DummyUpdateAction(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, debate: Debate) -> None:
        super(DummyUpdateAction, self).__init__(name)
        self.debate = debate

    def update(self) -> py_trees.common.Status:
        self.debate.update("パイナップルは蜜柑より甘い")
        self.debate.update("バナナはりんごより甘い")
        self.debate.update("蜜柑はどんな果物よりも甘い")
        self.debate.update("りんごは甘くない")

        return py_trees.common.Status.SUCCESS

    def initialise(self) -> None:
        pass


class UpdateAction(py_trees.behaviour.Behaviour):
    def __init__(
        self,
        name: str,
        debate: Debate,
        fetch_comment_callback: Callable,
        num_get_comment: int,
    ) -> None:
        super(UpdateAction, self).__init__(name)
        self.debate = debate
        self.loader = fetch_comment_callback
        self.num_get_comment = num_get_comment

    def update(self) -> py_trees.common.Status:
        for _ in range(self.num_get_comment):
            comment = self.loader()
            assert isinstance(comment, str)
            self.debate.update(comment)

            time.sleep(5)

        return py_trees.common.Status.SUCCESS

    def initialise(self) -> None:
        pass


class WaitingAction(py_trees.behaviour.Behaviour):
    def __init__(self, name: str, waiting_callback: Callable[[], bool]) -> None:
        super().__init__(name)
        self.waiting_callback = waiting_callback

    def update(self) -> py_trees.common.Status:
        while True:
            if self.waiting_callback():
                break
            time.sleep(1)

        return py_trees.common.Status.SUCCESS

    def initialise(self) -> None:
        pass


class PlayAgainAction(py_trees.behaviour.Behaviour):
    def __init__(self, name: str) -> None:
        super(PlayAgainAction, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(
            key="play_again_status", access=py_trees.common.Access.WRITE
        )

    def initialise(self) -> None:
        pass

    def update(self) -> py_trees.common.Status:
        cont = input("もう一度行いますか？ (y/n): ").lower()
        if cont == 'y':
            self.blackboard.play_again_status = py_trees.common.Status.SUCCESS
            return py_trees.common.Status.SUCCESS
        else:
            print("終了します。")
            self.blackboard.play_again_status = py_trees.common.Status.FAILURE
            return py_trees.common.Status.FAILURE
