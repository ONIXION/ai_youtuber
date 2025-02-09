"""
WebRTCを使用したブラウザ画面共有サーバー

このモジュールは、WebRTCを利用してブラウザの画面をキャプチャし、
クライアントにストリーミングするサーバーを実装します。
"""

import asyncio
import json
import logging
import ssl
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from fractions import Fraction
from logging import Formatter, StreamHandler, getLogger
from typing import Any

import av
import mss
import numpy as np
import requests  # type: ignore
import websocket
from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
)
from browser_use import Agent, Controller
from browser_use.browser.browser import (
    Browser,
    BrowserConfig,
    BrowserContext,
    BrowserContextConfig,
)
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

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
    logger = getLogger("__main__").getChild(__name__)
    logger.setLevel(logging.WARNING)


@dataclass
class WindowBounds:
    """ウィンドウの位置・サイズを表すデータクラス"""

    x: int
    y: int
    width: int
    height: int


class BrowserController:
    """ブラウザの制御を行うクラス"""

    def __init__(self, port_list: list, window_bounds_list: list[WindowBounds]) -> None:
        """初期化

        Args:
            port_list (list): cdpポート番号のリスト
            window_bounds_list (list[WindowBounds]): ウィンドウの位置・サイズのリスト
        """
        self.browser_list: list = []

        assert len(port_list) == len(window_bounds_list)
        self.port_list = port_list
        self.window_bounds_list = window_bounds_list

    def start_chrome(self) -> list[subprocess.Popen]:
        """Chromeを起動する"""
        return [
            self._start_chrome(port, f"temp/chrome-{port}") for port in self.port_list
        ]

    def _start_chrome(self, port: int, user_data_dir: str) -> subprocess.Popen:
        """
        指定ポートのDevTools Protocolを開放してChromeを起動。
        Xvfbを用いて仮想ディスプレイ上でChromeを起動します。
        ユーザーデータディレクトリも個別に指定するとセッションが干渉しにくくなります。
        """
        cmd = [
            # "xvfb-run",
            # "--auto-servernum",
            "/usr/bin/google-chrome",
            f"--remote-debugging-port={port}",
            f"--remote-allow-origins=http://127.0.0.1:{port}",
            f"--user-data-dir={user_data_dir}",
            "--disable-background-networking",
            "--no-first-run",
            "--no-default-browser-check",
            "https://example.com",
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _get_target_info(self, port: int) -> list[dict]:
        """CDPエンドポイントから全ターゲット情報を取得し、最初のものを返す"""
        resp = requests.get(f"http://127.0.0.1:{port}/json")
        targets = resp.json()
        if not targets:
            raise Exception("No targets found")

        assert isinstance(targets, list)
        return targets

    def _get_window_id(self, port: int, target_id: str) -> Any:
        """指定target_idに対してBrowser.getWindowForTargetを実行し、windowIdを返す"""
        # まず、対象のwebSocketDebuggerUrlを取得
        resp = requests.get(f"http://127.0.0.1:{port}/json")
        targets = resp.json()
        ws_url = None
        for target in targets:
            if target.get("id") == target_id:
                ws_url = target.get("webSocketDebuggerUrl")
                break
        if ws_url is None:
            raise Exception("Target not found for given port and target_id")

        # WebSocket接続を確立
        ws = websocket.create_connection(ws_url)
        message_id = 1
        command = {
            'id': message_id,
            'method': 'Browser.getWindowForTarget',
            'params': {},
        }
        ws.send(json.dumps(command))
        result = json.loads(ws.recv())
        ws.close()
        if "result" in result:
            return result["result"]["windowId"]
        else:
            raise Exception("Failed to get window ID")

    def get_unique_window_ids(self, port: int) -> list[int]:
        """
        指定されたポート内のCDPエンドポイントから全ターゲット情報を取得し、
        各ターゲットに対して getWindowForTarget を実行してウィンドウIDを取得します。
        重複するIDは含めず、ユニークなウィンドウIDのリストを返します。
        """
        unique_ids = set()
        window_ids = []
        try:
            targets = self._get_target_info(port)
        except Exception as e:
            print(f"ポート {port} からターゲット情報を取得できませんでした: {e}")

        for target in targets:
            target_id = target.get("id")
            if not target_id:
                continue
            try:
                wid = self._get_window_id(port, target_id)
                if wid not in unique_ids:
                    unique_ids.add(wid)
                    window_ids.append(wid)
            except Exception as e:
                print(
                    f"ポート {port} の対象 (target_id: {target_id}) からウィンドウIDを取得できませんでした: {e}"
                )
        return window_ids

    def set_window_bounds(self) -> None:
        """管理対象の全てのウィンドウの位置・サイズを設定"""
        for port, window_bounds in zip(self.port_list, self.window_bounds_list):
            window_ids = self.get_unique_window_ids(port)
            for window_id in window_ids:
                self._set_window_bounds(
                    port,
                    window_id,
                    window_bounds.x,
                    window_bounds.y,
                    window_bounds.width,
                    window_bounds.height,
                )

    def _set_window_bounds(
        self, port: int, window_id: int, x: int, y: int, width: int, height: int
    ) -> Any:
        """CDP経由で特定のポート内のウィンドウの位置・サイズを設定"""
        # まず、任意のターゲットのWebSocket URLを取得
        target = self._get_target_info(port)[0]
        ws_url = target["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url)
        message_id = 1
        bounds = {
            "left": x,
            "top": y,
            "width": width,
            "height": height,
            "windowState": "normal",
        }
        command = {
            "id": message_id,
            "method": "Browser.setWindowBounds",
            "params": {"windowId": window_id, "bounds": bounds},
        }
        ws.send(json.dumps(command))
        result = json.loads(ws.recv())
        ws.close()
        return result

    @staticmethod
    def get_devtools_url(port: int) -> str:
        """
        DevTools ProtocolのWebSocketエンドポイント(例: ws://127.0.0.1:<port>/devtools/browser/<id>)を取得。
        """
        max_retries = 10
        delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/json/version")
                info = resp.json()
                url = info["webSocketDebuggerUrl"]  # DevTools Protocol用WebSocket URL
                assert isinstance(url, str)
                return url
            except requests.RequestException:
                pass
            time.sleep(delay)

        raise Exception("Failed to get DevTools Protocol URL.")

    def cleanup(self) -> None:
        """Clean up browser resources."""
        if self.browser_list:
            for browser in self.browser_list:
                browser.quit()


class ScreenCaptureTrack(MediaStreamTrack):
    """画面キャプチャ用のMediaTrackクラス"""

    kind = "video"

    def __init__(self) -> None:
        super().__init__()
        self.sct = mss.mss()
        monitors = self.sct.monitors

        # プライマリモニターまたは利用可能な唯一のモニターを選択
        self._monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        # キャプチャ範囲を1280x825に設定
        self._monitor = {
            "left": self._monitor["left"],
            "top": self._monitor["top"],
            "width": 1280,
            "height": 825,
        }

        self._timestamp = 0
        self._frame_rate = 30

    async def next_timestamp(self) -> tuple:
        """タイムスタンプを生成"""
        pts = self._timestamp
        self._timestamp += 1
        return pts, Fraction(1, self._frame_rate)

    async def recv(self) -> av.VideoFrame:
        """Capture screen and return a video frame."""
        try:
            screen = self.sct.grab(self._monitor)  # RGBA 32bit
            # 画像フォーマットの変換
            img = np.array(screen)
            frame = av.VideoFrame.from_ndarray(img, format="bgra")
            pts, time_base = await self.next_timestamp()
            frame.pts = pts
            frame.time_base = time_base
            return frame

        except Exception as e:
            print(f"Error capturing frame: {e}")
            raise


class webRTCServer:
    def __init__(
        self, port_list: list[int], window_bounds_list: list[WindowBounds]
    ) -> None:
        self.pcs: dict = {}
        self.port_list = port_list
        self.browser_controller: BrowserController = BrowserController(
            self.port_list, window_bounds_list
        )

    async def offer(self, request: web.Request) -> web.Response:
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        # Generate unique ID for this connection
        connection_id = str(uuid.uuid4())
        pc = RTCPeerConnection()
        self.pcs[connection_id] = pc

        # 接続状態の監視
        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if pc.connectionState == "failed":
                await pc.close()
                self.pcs.discard(pc)  # type: ignore

        # ICE接続状態の監視
        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange() -> None:
            pass

        # Add screen capture track with optimized settings
        video = ScreenCaptureTrack()
        pc.addTrack(video)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {
                    "sdp": pc.localDescription.sdp,
                    "type": pc.localDescription.type,
                    "connectionId": connection_id,
                }
            ),
        )

    def parse_candidate(self, candidate_str: str) -> dict | None:
        # candidate:1920441499 1 tcp 1518283007 240d:1e:126:8605:3beb:aee7:7c31:ac39 51846 typ host tcptype passive ...
        parts = candidate_str.split()
        if not parts[0].startswith("candidate:"):
            return None

        foundation = parts[0].split(":")[1]
        component = int(parts[1])
        protocol = parts[2]
        priority = int(parts[3])
        ip = parts[4]
        port = int(parts[5])

        # find type
        try:
            type_index = parts.index("typ")
            candidate_type = parts[type_index + 1]
        except ValueError:
            candidate_type = "host"  # default type

        return {
            "foundation": foundation,
            "component": component,
            "protocol": protocol,
            "priority": priority,
            "ip": ip,
            "port": port,
            "type": candidate_type,
        }

    async def handle_candidate(self, request: web.Request) -> web.Response:
        """ICE candidateの処理を行う"""
        params = await request.json()
        connection_id = params.get("connectionId")

        if not connection_id or connection_id not in self.pcs:
            return web.Response(status=400, text="Invalid connection ID")

        pc = self.pcs[connection_id]
        candidate_str = params["candidate"]
        sdp_mid = params.get("sdpMid")
        sdp_mline_index = params.get("sdpMLineIndex", 0)

        parsed = self.parse_candidate(candidate_str)
        if parsed is None:
            return web.Response(status=400, text="Invalid candidate string")

        candidate = RTCIceCandidate(
            foundation=parsed["foundation"],
            component=parsed["component"],
            protocol=parsed["protocol"],
            priority=parsed["priority"],
            ip=parsed["ip"],
            port=parsed["port"],
            type=parsed["type"],
            sdpMid=sdp_mid,
            sdpMLineIndex=sdp_mline_index,
        )

        await pc.addIceCandidate(candidate)
        return web.Response(text="OK")

    async def on_shutdown(self, app: web.Application) -> None:
        """アプリケーションのシャットダウン時の処理"""
        # WebRTC接続のクリーンアップ
        coros = [pc.close() for pc in self.pcs.values()]
        await asyncio.gather(*coros)
        self.pcs.clear()

        # ブラウザのクリーンアップ
        if hasattr(app, 'browser_controller'):
            app['browser_controller'].cleanup()

    async def periodic_set_window_bounds(self, interval: float = 0.5) -> None:
        """定期的に set_window_bounds を実行するタスク（interval秒ごと）"""
        while True:
            try:
                self.browser_controller.set_window_bounds()
            except Exception as e:
                print(f"ウィンドウ境界サイズ更新エラー: {e}")
            await asyncio.sleep(interval)

    async def _start(self) -> None:
        """WebRTCサーバーのメインエントリーポイント"""
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain("./cert/server.crt", "./cert/server.key")

        # アプリケーションの設定
        app = web.Application()
        app.on_shutdown.append(self.on_shutdown)
        app.router.add_post("/offer", self.offer)
        app.router.add_post("/candidate", self.handle_candidate)

        # ブラウザコントローラーの初期化と起動
        app['browser_controller'] = self.browser_controller

        # ブラウザの起動
        self.browser_controller.start_chrome()

        # このディレイは必要
        await asyncio.sleep(5)

        # ブラウザの初期設定
        self.browser_controller.set_window_bounds()

        # 定期的にウィンドウの位置・サイズを更新するタスクを開始
        bounds_task = asyncio.create_task(self.periodic_set_window_bounds())

        # サーバーの起動
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8443, ssl_context=ssl_context)
        await site.start()

        logger.info("WebRTC server started")
        try:
            await asyncio.Event().wait()
            logger.info("WebRTC server stopped")
        finally:
            bounds_task.cancel()
            await runner.cleanup()

    def start(self) -> None:
        """WebRTCサーバーの起動"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start())
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


async def run_agent_task(port: int) -> None:
    """テスト用のエージェントタスク"""
    browser = Browser(
        config=BrowserConfig(cdp_url=BrowserController.get_devtools_url(port))
    )
    config = BrowserContextConfig(
        browser_window_size={'width': 600, 'height': 825},
    )
    context = BrowserContext(browser=browser, config=config)
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task="蜜柑は英語で何という？",
        llm=model,
        controller=Controller(),
        browser_context=context,
    )
    await agent.run()
    await asyncio.sleep(1)


if __name__ == "__main__":
    port_list = [9222, 9223]
    window_bounds_list = [
        WindowBounds(0, 0, 600, 600),
        WindowBounds(640, 0, 600, 600),
    ]
    server = webRTCServer(port_list=port_list, window_bounds_list=window_bounds_list)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()

    time.sleep(10)
    logger.info("Server started.")

    input(
        "Unityを起動し、webRTCの接続が確認出来たら、任意のキーを押して続行してください\n"
    )

    async def main_agent_tasks() -> None:
        """メインスレッド用のエージェントタスクを並列で実行"""
        await asyncio.gather(
            run_agent_task(9222),
            run_agent_task(9223),
        )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_agent_tasks())

    logger.info("All agent tasks completed.")
    while True:
        time.sleep(1)
        pass
