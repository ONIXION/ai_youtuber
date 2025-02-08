import asyncio
import json
import subprocess
import sys
import threading
from typing import Optional, Set

from websockets.legacy.server import WebSocketServerProtocol, serve


def start_server_log_receiver() -> subprocess.Popen:
    """
    サーバー用ログ受信用のターミナルを新規起動する。
    cmd の /k オプションにより、スクリプト終了後もターミナルを維持します。
    """
    return subprocess.Popen(
        [sys.executable, "src/test/dummy_unity_client.py"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


class WebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
        # Unity側では以下のように設定する
        # Uri serverUri = new Uri("ws://34.133.108.164:5000");
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server: serve | None = None
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.unity_flag = False  # これがTrueの時だけコメントを抽選
        self.debug = debug
        self._dummy_client: subprocess.Popen | None = None

    def __del__(self) -> None:
        """デコンストラクタ"""
        self.stop()

    async def _handle_client(
        self, websocket: WebSocketServerProtocol, path: str
    ) -> None:
        """クライアント接続を処理するコルーチン"""
        try:
            # クライアントを登録
            self.clients.add(websocket)
            print(f"Client connected. Total clients: {len(self.clients)}")

            # メインループ
            while True:
                try:
                    # 接続状態を確認
                    if websocket.closed:
                        print("Client connection closed")
                        break

                    # メッセージ受信
                    message = await websocket.recv()
                    if not message:
                        print("Received empty message")
                        continue

                    try:
                        data = json.loads(message)
                        if 'message' in data:
                            print(f"Received message: {data['message']}")
                            if data['message'] == 'Finish':
                                self.unity_flag = True
                        else:
                            print(f"Received invalid message format: {data}")
                    except json.JSONDecodeError:
                        print(f"Received non-JSON message: {message}")
                        # 無効なメッセージの場合はエラーを返す
                        error_message = json.dumps({"error": "Invalid JSON format"})
                        await self._send_message(
                            websocket,
                            name="Server",
                            reply=error_message,
                            action="Error",
                            emotion="normal",
                            scene="",
                        )

                except asyncio.CancelledError:
                    print("Client connection cancelled")
                    break
                except ConnectionError:
                    print("Client connection lost")
                    break
                except Exception as e:
                    print(f"Client connection error: {str(e)}")
                    break

        except Exception as e:
            print(f"Client handler error: {str(e)}")
        finally:
            # クライアントの登録解除
            if websocket in self.clients:
                self.clients.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.clients)}")

    def start(self) -> None:
        """サーバーを別スレッドで開始"""
        if self.debug:
            print("Creating new dummy client for server log")
            self._dummy_client = start_server_log_receiver()
            # 待機
            asyncio.run(asyncio.sleep(1))

        if self._server_thread is not None:
            print("Server is already running")
            return

        def run_server() -> None:
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

                async def start_ws_server() -> None:
                    self.server = await serve(self._handle_client, self.host, self.port)
                    print(f"WebSocket server started at ws://{self.host}:{self.port}")
                    await self.server.wait_closed()

                self._loop.run_until_complete(start_ws_server())
                self._loop.run_forever()
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print(f"Server error: {str(e)}")
                self.stop()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

    def stop(self) -> None:
        """サーバーを停止"""
        if self._loop is None:
            return

        async def cleanup() -> None:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            for client in self.clients:
                await client.close()
            self.clients.clear()

        if self._loop.is_running():
            self._loop.create_task(cleanup())
            self._loop.stop()
        self._server_thread = None
        self._loop = None
        print("WebSocket server stopped")

        # ダミークライアントのプロセスがあれば終了する
        if self._dummy_client is not None:
            try:
                self._dummy_client.terminate()
                self._dummy_client.wait(timeout=5)
                print("Dummy client process terminated.")
            except Exception as e:
                print(f"Failed to terminate dummy client process: {e}")
            finally:
                self._dummy_client_process = None

    async def _send_message(
        self,
        client: WebSocketServerProtocol,
        name: str,
        reply: str,
        action: str,
        emotion: str,
        scene: str,
    ) -> None:
        """単一のクライアントにメッセージを送信"""
        if client is None or client.closed:
            print("Cannot send message - client is disconnected")
            self.clients.discard(client)
            return
        try:
            message = json.dumps(
                {
                    "name": name,
                    "content": reply,
                    "action": action,
                    "emotion": emotion,
                    "scene": scene,
                }
            )
            await client.send(message)

        except Exception as e:
            print(f"Failed to send message: {str(e)}")
            self.clients.discard(client)

    def send_message_to_all(
        self, name: str, reply: str, action: str, emotion: str, scene: str
    ) -> None:
        """全クライアントにメッセージを送信"""
        if self._loop is None or not self._loop.is_running():
            print("Server is not running")
            return

        async def broadcast() -> None:
            if not self.clients:
                print("No connected clients")
                return
            try:
                await asyncio.gather(
                    *[
                        self._send_message(
                            client,
                            name=name,
                            reply=reply,
                            action=action,
                            emotion=emotion,
                            scene=scene,
                        )
                        for client in self.clients
                    ]
                )
            except Exception as e:
                print(f"Broadcast error: {str(e)}")

        asyncio.run_coroutine_threadsafe(broadcast(), self._loop)


# 使用例
if __name__ == "__main__":
    # サーバーのインスタンスを作成
    server = WebSocketServer(port=5000)
    try:
        # サーバーを開始（別スレッドで実行）
        server.start()
        # メインスレッドでの操作例
        while True:
            message = input("Enter message to send (or 'quit' to exit): ")
            if message.lower() == 'quit':
                break
            server.send_message_to_all(
                name="server", reply=message, action="Test", emotion="normal", scene=""
            )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()
