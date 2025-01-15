# python -m src.main

import asyncio
import logging
import subprocess
import tkinter as tk
from logging import Formatter, StreamHandler, getLogger
from tkinter import simpledialog
from typing import Callable

from src.ai_tuber import AItuber, TalkFormat, TalkInput
from src.connect_unity import WebSocketServer
from src.youtube import YouTubeLiveChat

# ログの設定
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(handler_format)
logger.addHandler(stream_handler)

WEBSOCKET_SERVER_PORT = 5000
AIvisSpeech_EXECUTABLE = (
    r"C:\Users\kousei\AppData\Local\Programs\AivisSpeech\AivisSpeech.exe"
)
BouyomiChan_EXECUTABLE = (
    r"C:\Users\kousei\AppData\Local\BouyomiChan_0_1_11_0_Beta21\BouyomiChan.exe"
)
UnityApp_EXECUTABLE = r"C:\Users\kousei\AppDev\AItuber\Builds\AItuber.exe"


class YoutubeLive:
    def __init__(self) -> None:
        """必要なプロセスを起動し、AItuberを開始する"""
        # WebSocketサーバーを開始
        self.unity_server = WebSocketServer(port=WEBSOCKET_SERVER_PORT)
        self.unity_server.start()
        self.youtube = YouTubeLiveChat(self.unity_server)
        # subprocessを開始
        subprocess.Popen(
            [AIvisSpeech_EXECUTABLE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.Popen(
            [BouyomiChan_EXECUTABLE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.Popen(
            [UnityApp_EXECUTABLE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # 5秒待機
        asyncio.run(asyncio.sleep(5))

        # AItuberを開始
        self.aituber = AItuber(
            response_callback=self.create_send_unity_callback(self.unity_server)
        )
        logger.info("AItuberを開始しました")

    def __del__(self) -> None:
        """デコンストラクタ"""
        self.close()

    def create_send_unity_callback(
        self, server: WebSocketServer
    ) -> Callable[[str], None]:
        """Unityにメッセージを送信するためのコールバック関数を生成する

        Args:
            server (WebSocketServer): WebSocketサーバー

        Returns:
            Callable[[str], None]: AIからのメッセージを受け取り、Unityに送信するコールバック関数
        """

        def send_unity_callback(response: str) -> None:
            message = TalkFormat.model_validate_json(response)
            server.send_message_to_all(
                reply=message.reply, action=message.action, emotion=message.emotion
            )

        return send_unity_callback

    def get_youtube_url(self) -> str:
        """YouTube Live配信のURLを取得する

        Returns:
            str: YouTube Live配信のURL
        """
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        url = simpledialog.askstring(
            "Input", "YouTube Live配信のURLを入力してください:"
        )
        assert isinstance(url, str)
        return url

    async def reply_comment(self) -> None:
        """コメントに返信する、コメントがない場合は何もしない"""
        comment = self.youtube.get_random_comment()
        if comment is None:
            return
        name, input = comment['author'], comment['text']
        if name and input:
            self.unity_server.send_message_to_all(
                reply=input, action="Message", emotion=name
            )
            agent_input = TalkInput(name=name, input=input).model_dump_json()
            await self.aituber.graph.ainvoke({"messages": [agent_input]})

    async def start_monitoring(self) -> None:
        """モニタリングを開始する"""
        logger.info("モニタリングを開始します")

        # 設定が完了するまで待機
        print("YoutubeLiveを開始し、ストリーミングの設定を行って下さい")
        print("設定が完了したらEnterキーを押してください")
        while True:
            input_text = input()
            if input_text == "":
                break

        # YouTube LiveチャットのURLを取得
        video_url = self.get_youtube_url()
        if video_url is None or video_url.strip() == "":
            logger.error("URLが入力されていません。終了します。")
            return
        self.youtube.start_monitoring(video_url)

        while True:
            await self.reply_comment()
            await asyncio.sleep(0.5)

    def close(self) -> None:
        """終了処理"""
        logger.info("YoutubeLiveを終了します")
        self.unity_server.stop()
        self.youtube.stop_monitoring()
        subprocess.run(["taskkill", "/f", "/im", "AivisSpeech.exe"])
        subprocess.run(["taskkill", "/f", "/im", "BouyomiChan.exe"])
        subprocess.run(["taskkill", "/f", "/im", "AItuber.exe"])


if __name__ == "__main__":
    # 初期化
    youtube_live = YoutubeLive()
    try:
        # モニタリングを開始
        asyncio.run(youtube_live.start_monitoring())
    except KeyboardInterrupt:
        # Ctrl+Cが押された場合に終了処理を実行
        logger.info("終了コマンドを受信しました")
    finally:
        # デコンストラクタを呼び出すことで終了処理を実行
        del youtube_live
