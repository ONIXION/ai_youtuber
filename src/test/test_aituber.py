# python -m src.test.test_aituber
import asyncio
import subprocess
from typing import Callable
from unittest.mock import patch

import pytest

from src.ai_tuber import AItuber, TalkFormat, TalkInput
from src.connect_unity import WebSocketServer

WEBSOCKET_SERVER_PORT = 5000
AIvisSpeech_EXECUTABLE = (
    r"C:\Users\kousei\AppData\Local\Programs\AivisSpeech\AivisSpeech.exe"
)
BouyomiChan_EXECUTABLE = (
    r"C:\Users\kousei\AppData\Local\BouyomiChan_0_1_11_0_Beta21\BouyomiChan.exe"
)
UnityApp_EXECUTABLE = r"C:\Users\kousei\AppDev\AItuber\Builds\AItuber.exe"


def print_response_callback(response: str) -> None:
    message = TalkFormat.model_validate_json(response)
    print(f"AI callback: {message.reply}")
    print(f"AI callback: {message.emotion}")
    print(f"AI callback: {message.action}")


def create_send_unity_callback(server: WebSocketServer) -> Callable[[str], None]:
    def send_unity_callback(response: str) -> None:
        message = TalkFormat.model_validate_json(response)
        server.send_message_to_all(
            reply=message.reply, action=message.action, emotion=message.emotion
        )

    return send_unity_callback


async def console_app() -> None:
    aituber = AItuber(response_callback=print_response_callback)
    while True:
        user_input = input("ユーザー: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("終了します...")
            break
        agent_input = TalkInput(name="初期設定", input=user_input).model_dump_json()
        response: dict = await aituber.graph.ainvoke({"messages": [agent_input]})
        response_content: TalkFormat = TalkFormat.model_validate_json(
            response['messages'][-1].content
        )
        print(f"AI: {response_content.reply}")
        print(f"AI: {response_content.emotion}")
        print(f"AI: {response_content.action}")


async def unity_solo_live() -> None:
    # WebSocketサーバーを開始
    unity_server = WebSocketServer(port=WEBSOCKET_SERVER_PORT)
    unity_server.start()
    # subprocessを開始
    subprocess.Popen(
        [AIvisSpeech_EXECUTABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.Popen(
        [BouyomiChan_EXECUTABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.Popen(
        [UnityApp_EXECUTABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    await asyncio.sleep(5)

    # AItuberを開始
    aituber = AItuber(response_callback=create_send_unity_callback(unity_server))

    # ユーザー入力を処理
    while True:
        user_input = input("ユーザー: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("終了します...")
            break
        agent_input = TalkInput(name="リスナー１", input=user_input).model_dump_json()
        response: dict = await aituber.graph.ainvoke({"messages": [agent_input]})
        response_content: TalkFormat = TalkFormat.model_validate_json(
            response['messages'][-1].content
        )
        print(f"AI: {response_content.reply}")
        print(f"AI: {response_content.emotion}")
        print(f"AI: {response_content.action}")

    # WebSocketサーバーを停止
    unity_server.stop()
    # subprocessを終了
    subprocess.run(["taskkill", "/f", "/im", "AivisSpeech.exe"])
    subprocess.run(["taskkill", "/f", "/im", "BouyomiChan.exe"])
    subprocess.run(["taskkill", "/f", "/im", "AItuber.exe"])


def run_console_app() -> None:
    asyncio.run(console_app())


def test_console_app() -> None:
    with patch("builtins.input", side_effect=["こんにちは", "exit"]):
        asyncio.run(console_app())


def run_unity_solo_live() -> None:
    asyncio.run(unity_solo_live())


# TODO:AivisSpeechが開始されない問題を解決する
def test_unity_solo_live() -> None:
    with patch("builtins.input", side_effect=["こんにちは", "exit"]):
        asyncio.run(unity_solo_live())


if __name__ == "__main__":
    # pytest.main(['-v', '-s', 'src/test/test_aituber.py'])
    run_unity_solo_live()
