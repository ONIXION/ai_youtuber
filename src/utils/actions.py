import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from logging import Formatter, StreamHandler, getLogger
from typing import Callable, List

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
        send_message_callback: Callable | None = None,
        waiting_callback: Callable[[], bool] = lambda: False,
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
        self.blackboard.register_key(
            key="conversation_history", access=py_trees.common.Access.WRITE
        )
        self.send_message_callback = send_message_callback
        logger.info(f"AgentAction: {name} を初期化しました")
        self.waiting_callback = waiting_callback

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
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            future = asyncio.ensure_future(
                agent.graph.ainvoke({"messages": [agent_input]}),
                loop=loop
            )
            response = loop.run_until_complete(future)
            message = TalkFormat.model_validate_json(
                response["messages"][-1].content
            ).reply
            setattr(self.blackboard, f"{agent_key}_response", message)
            self.blackboard.last_speaker = agent_key
            # 会話履歴を更新
            conversation_history = getattr(self.blackboard, "conversation_history", [])
            conversation_history.append(f"{agent_key}: {message}")
            self.blackboard.conversation_history = conversation_history
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
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            future = asyncio.ensure_future(
                asyncio.gather(
                    agent1.graph.ainvoke({"messages": [agent1_input]}),
                    agent2.graph.ainvoke({"messages": [agent2_input]}),
                ),
                loop=loop
            )
            responses = loop.run_until_complete(future)
            response1, response2 = responses
            assert response1 is not None and response2 is not None

            message1 = TalkFormat.model_validate_json(
                response1["messages"][-1].content
            ).reply
            message2 = TalkFormat.model_validate_json(
                response2["messages"][-1].content
            ).reply

            setattr(self.blackboard, f"{agent1_key}_response", message1)
            setattr(self.blackboard, f"{agent2_key}_response", message2)
            
            logger.debug(f"AgentAction: {agent1_key} の応答: {message1}")
            logger.debug(f"AgentAction: {agent2_key} の応答: {message2}")

            # 会話履歴を更新
            conversation_history = getattr(self.blackboard, "conversation_history", [])
            conversation_history.extend([
                f"{agent1_key}: {message1}",
                f"{agent2_key}: {message2}"
            ])
            self.blackboard.conversation_history = conversation_history

        except Exception as e:
            raise e

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
        send_message_callback: Callable,
    ) -> None:
        super().__init__(name, agent_dict, send_message_callback)
        self.loader = fetch_comment_callback

    def generate_prompt(self) -> str:
        assert self.send_message_callback is not None
        self.send_message_callback(
            name="host",
            reply="これからお二人には視聴者が気になるテーマについて話し合って頂きましょう。視聴者の皆さんはお二人に議論してほしい話題をコメントで送って下さい。",
            action="",
            emotion="",
            scene="conversation",
        )

        # TODO: 待機時間を設定するべき？

        comment = self.loader()
        assert isinstance(comment, str)

        self.send_message_callback(
            name="host",
            reply=f"今回の話題は以下の通りです: {comment}。お二人にはこの話題について話し合って頂きましょう。",
            action="",
            emotion="",
            scene="",
        )

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
        send_message_callback: Callable,
        mode: str = "WebSearch",
        waiting_callback: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__(name, agent_dict, send_message_callback)
        self.loader = create_agenda_callback
        self.agenda: str = ""
        self.agenda_list: list[str] = ["", ""]
        self.debate = debate
        self.mode = mode
        self.waiting_callback = waiting_callback

    def start_new_debate(self) -> None:
        assert self.send_message_callback is not None
        self.agenda = self.loader()
        assert isinstance(self.agenda, str), "agendaはstr型である必要があります"

        self.send_message_callback(
            name="host",
            reply=f"今回のディベートのテーマは以下の通りです:\n {self.agenda}",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback():
            time.sleep(0.1)

        self.send_message_callback(
            name="system",
            reply="",
            action="",
            emotion="",
            scene="debate",
        )
        time.sleep(0.1)

        self.send_message_callback(
            name="host",
            reply="お二人にはこのテーマについて賛成と反対に分かれてディベートして頂きます。",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback():
            time.sleep(0.1)

        self.send_message_callback(
            name="host",
            reply="最初にシンキングタイムが与えられますので、あなたの主張を裏付ける根拠を調べて、準備してください。",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback():
            time.sleep(0.1)

        # self.send_message_callback(
        #     name="host",
        #     reply="ディベートの勝敗は視聴者の皆さんによって決定されます。お二人の意見を聞いて、どちらが正しいと思うかコメントで教えて下さい。",
        #     action="",
        #     emotion="",
        #     scene="",
        # )

        self.agenda_list[0] = f"{self.agenda}は正しい"
        self.agenda_list[1] = f"{self.agenda}は誤り"

        # Initialize debate and conversation history
        names = list(self.agent_dict.keys())
        self.debate.init_new_debate(names=names, arguments=self.agenda_list)

        # Initialize conversation history with debate topic and initial positions
        self.blackboard.conversation_history = [
            f"ディベートトピック: {self.agenda}",
            f"{names[0]} (賛成派): {self.agenda_list[0]}",
            f"{names[1]} (反対派): {self.agenda_list[1]}"
        ]

    def generate_prompt(self) -> list[str]:
        self.start_new_debate()

        if self.mode == "WebSearch":
            prompt_prefix = (
                "これから相方とディベートを行ってもらいます。あなたは以下の主張を正当化し、相方を論破しなければなりません。",
                "最初にシンキングタイムが与えられますので、あなたの主張を裏付ける根拠を調べて、準備してください。自らの主張に不都合な事実は無視してください:\n",
                "かならずWebSearchを使用してください\n",
                "主張：",
            )
        elif self.mode == "Think":
            prompt_prefix = (
                "これから相方とディベートを行ってもらいます。あなたは以下の主張を正当化し、相方を論破しなければなりません。",
                "最初にシンキングタイムが与えられますので、あなたの主張を裏付ける根拠を考えて、準備してください。:\n",
                "かならずThinkを使用してください\n",
                "主張：",
            )
        else:
            raise ValueError("modeは'WebSearch'または'Think'である必要があります")
        prompt1 = "\n".join(prompt_prefix) + self.agenda_list[0]
        prompt2 = "\n".join(prompt_prefix) + self.agenda_list[1]
        return [prompt1, prompt2]


class StartDebateAction(BaseAgentAction):
    def generate_prompt(self) -> str:
        self.send_message_callback(
            name="host",
            reply="シンキングタイムが終了しました。ディベートを開始してください。",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback():
            time.sleep(1)
        prompt = (
            "シンキングタイムが終了しました。ディベートを開始します。最初に、できるだけ短く，簡潔にあなたの論証を相方に対して述べてください。"
            "多少の無理があろうと，決して自らの主張を曲げず，適宜自分の考えで論理を補足してください．"
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

        self.send_message_callback(
            name="host",
            reply="相手の主張に反論してください",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback():
            time.sleep(1)

        prompt_prefix = (
            "あなたの相方は以下のように発言しました。これに対してシンキングタイムで考えた内容をもとに、できるだけ短く，簡潔に反論してください:\n",
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
        send_message_callback: Callable,
        waiting_callback: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__(name, agent_dict, send_message_callback)
        self.debate = debate
        self.waiting_callback = waiting_callback

    def generate_prompt(self) -> list[str]:
        assert self.send_message_callback is not None
        # 会話履歴を取得
        conversation_history = getattr(self.blackboard, "conversation_history", [])
        self.send_message_callback(
            name="host",
            reply="ディベートが終了しました。結果を集計して発表します。",
            action="",
            emotion="",
            scene="",
        )
        # 会話履歴を使用して勝者を判定
        winner = self.debate.judge_winner(conversation_history) # agent1 or agent2
        self.send_message_callback(
            name="host",
            reply=f"今回のディベートの勝者は{self.agent_dict[winner].name}です。おめでとうございます！",
            action="",
            emotion="",
            scene="",
        )
        while not self.waiting_callback(): # タイミングがずれてここで止まってしまう
            time.sleep(1)
        time.sleep(0.5)
        self.send_message_callback(
            name="system",
            reply="",
            action="",
            emotion="",
            scene="conversation",
        )
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
        while not self.waiting_callback():
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
