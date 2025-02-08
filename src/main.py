# python -m src.main

import asyncio
import logging
import subprocess
import tkinter as tk
from logging import Formatter, StreamHandler, getLogger
from tkinter import simpledialog
from typing import Callable

from dotenv import load_dotenv

from src.agent import TalkFormat
from src.agent_controller import DualAgentController
from src.connect_unity import WebSocketServer
from src.test.dummy_youtube import DummyYouTubeLiveChat
from src.youtube import YouTubeLiveChat

load_dotenv()


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
    def __init__(self, mode: str = "normal") -> None:
        """必要なプロセスを起動し、Liveの準備を行う"""
        assert mode in ["normal", "test"]
        # WebSocketサーバーを開始
        if mode == "normal":
            # self.unity_server = WebSocketServer(port=WEBSOCKET_SERVER_PORT)
            self.unity_server = WebSocketServer(port=WEBSOCKET_SERVER_PORT, debug=True)
        if mode == "test":
            self.unity_server = WebSocketServer(port=WEBSOCKET_SERVER_PORT, debug=True)
        self.unity_server.start()

        # YouTube Liveの設定
        if mode == "normal":
            self.youtube = YouTubeLiveChat(self.unity_server)
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

        elif mode == "test":
            self.youtube = DummyYouTubeLiveChat()

        # 必要なsubprocessを開始
        if not mode == "test":
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
                [UnityApp_EXECUTABLE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # 5秒待機
            asyncio.run(asyncio.sleep(5))

        # agent_controllerの初期化
        name_list = ["雲霧星奈", "星霧月音"]
        port_list = [9222, 9223]
        num_update_comment = 1  # ディベートの際に各ターンで取得するコメント数

        self.agent_controller = DualAgentController(
            name_list=name_list,
            port_list=port_list,
            response_callback_creater=self.response_callback_creator,
            conversation_agenda_callback=self.get_random_comment_callback,
            debate_agenda_callback=self.get_random_comment_callback,
            waiting_callback=self.waiting_callback,
            fetch_comment_callback=self.get_random_comment_callback,
            num_update_comment=num_update_comment,
            send_message_callback=self.unity_server.send_message_to_all,
        )

    def __del__(self) -> None:
        """デコンストラクタ"""
        self.close()

    def start(self) -> None:
        """対話を開始する"""
        self.agent_controller.start_dialog()

    def close(self) -> None:
        """終了処理"""
        logger.info("YoutubeLiveを終了します")
        self.unity_server.stop()
        self.youtube.stop_monitoring()
        subprocess.run(["taskkill", "/f", "/im", "AivisSpeech.exe"])
        subprocess.run(["taskkill", "/f", "/im", "BouyomiChan.exe"])
        subprocess.run(["taskkill", "/f", "/im", "AItuber.exe"])
        del self.agent_controller
        del self.youtube
        del self.unity_server

    def response_callback_creator(self, name: str) -> Callable[[str], None]:
        """Unityにメッセージを送信するためのコールバック関数を生成する

        Args:
            name (str): エージェントの名前

        Returns:
            Callable[[str], None]: Unityにメッセージを送信するためのコールバック関数
        """

        def send_unity_callback(response: str) -> None:
            """Unityにメッセージを送信する

            Args:
                response (str): エージェントの応答
            """
            message = TalkFormat.model_validate_json(response)
            self.unity_server.send_message_to_all(
                name=name,
                reply=message.reply,
                action=message.action,
                emotion=message.emotion,
                scene="",
            )

        return send_unity_callback

    def waiting_callback(self) -> bool:
        """Unityからの待機フラグを取得する

        Returns:
            bool: 待機フラグ
        """
        res = self.unity_server.unity_flag

        assert isinstance(res, bool)
        return res

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

    def get_random_comment_callback(self) -> str:
        while True:
            response = self.youtube.get_random_comment()
            if response is not None:
                break
            logger.info("コメントが取得できませんでした。再取得します...")
            asyncio.run(asyncio.sleep(5))

        res = response["text"]
        self.unity_server.send_message_to_all(
            name="message",
            reply=res,
            action="",
            emotion="",
            scene="",
        )

        assert isinstance(res, str)
        return res


if __name__ == "__main__":
    # 初期化
    youtube_live = YoutubeLive()
    try:
        # モニタリングを開始
        youtube_live.start()
    except KeyboardInterrupt:
        # Ctrl+Cが押された場合に終了処理を実行
        logger.info("終了コマンドを受信しました")
    finally:
        # デコンストラクタを呼び出すことで終了処理を実行
        del youtube_live
