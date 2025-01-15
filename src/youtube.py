import os
import pickle
import random
import threading
import time
from collections import deque
from typing import Any

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from connect_unity import WebSocketServer

load_dotenv()


class ThreadSafeComments:
    def __init__(self, maxlen: int = 1000) -> None:
        self.comments: deque[dict] = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self.last_accessed_time = time.time()

    def add_comment(self, author: str, text: str) -> None:
        with self.lock:
            self.comments.append(
                {'author': author, 'text': text, 'timestamp': time.time()}
            )

    def get_random_comment(self) -> dict | None:
        with self.lock:
            if not self.comments:
                return None
            current_time = time.time()
            # 30秒以上古いコメントを削除
            while self.comments and (current_time - self.comments[0]['timestamp']) > 30:
                self.comments.popleft()
            if not self.comments:
                return None
            # ランダムなindexを選択
            random_index = random.randint(0, len(self.comments) - 1)
            comment = self.comments[random_index]
            # random_indexより前のコメントを削除
            self.comments = deque(
                list(self.comments)[random_index + 1 :], maxlen=self.comments.maxlen
            )
            self.last_accessed_time = current_time
            return comment


class YouTubeLiveChat:
    def __init__(self, server: WebSocketServer, max_comments: int = 1000) -> None:
        """YouTubeライブチャット監視クラスの初期化"""
        self.comments_manager = ThreadSafeComments(maxlen=max_comments)
        self.youtube = self._initialize_youtube_api()
        self.monitoring_thread: threading.Thread | None = None
        self.is_monitoring = False
        self.processed_messages: set[dict] = set()
        self.server = server
        self.live_chat_id = None

    def _initialize_youtube_api(self) -> build:
        """YouTube APIクライアントの初期化"""
        # OAuth2の認証情報を読み込む
        credentials = None
        token_path = 'token.pickle'
        # 保存済みのトークンがあれば読み込む
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                credentials = pickle.load(token)

        # 認証情報がない、または無効な場合は新規に取得
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                # client_secrets.jsonが必要
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secrets.json',
                    scopes=['https://www.googleapis.com/auth/youtube.force-ssl'],
                )
                credentials = flow.run_local_server(port=8080)
            # トークンを保存
            with open(token_path, 'wb') as token:
                pickle.dump(credentials, token)

        return build('youtube', 'v3', credentials=credentials)

    def send_chat_message(self, message_text: str) -> dict | None:
        """ライブチャットにメッセージを送信"""
        if not self.live_chat_id:
            print("ライブチャットIDが取得できていません。")
            return None
        try:
            request = self.youtube.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": self.live_chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {"messageText": message_text},
                    }
                },
            )
            response = request.execute()
            print(f"メッセージを送信しました: {message_text}")
            return response
        except HttpError as e:
            print(f"メッセージ送信エラー: {e}")
            raise
        except Exception as e:
            print(f"予期せぬエラー: {e}")
            raise

    def _get_live_chat_id(self, video_id: str) -> str:
        """動画IDからライブチャットIDを取得"""
        try:
            response = (
                self.youtube.videos()
                .list(part='liveStreamingDetails', id=video_id)
                .execute()
            )

            items = response.get('items', [])
            if not items:
                raise ValueError(
                    f"動画ID {video_id} のライブチャットが見つかりません。"
                )
            live_details = items[0].get('liveStreamingDetails', {})
            live_chat_id = live_details.get('activeLiveChatId')
            if not live_chat_id:
                raise ValueError("ライブチャットIDが取得できません。")
            self.live_chat_id = live_chat_id

            assert isinstance(live_chat_id, str)
            return live_chat_id
        except HttpError as e:
            print(f"APIエラー: {e}")
            raise
        except Exception as e:
            print(f"エラー: {e}")
            raise

    def _get_live_chat_messages(self, live_chat_id: str, page_token: Any = None) -> Any:
        """ライブチャットのメッセージを取得"""
        try:
            return (
                self.youtube.liveChatMessages()
                .list(
                    liveChatId=live_chat_id,
                    part='snippet,authorDetails',
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as e:
            print(f"APIエラー: {e}")
            raise
        except Exception as e:
            print(f"エラー: {e}")
            raise

    def _monitor_live_chat(self, video_url: str, message_callback: Any = None) -> None:
        """
        ライブチャットを継続的にモニタリング
        Args:
            video_url (str): YouTubeの動画URL
            message_callback (callable, optional): 各メッセージを処理するコールバック関数
        """
        # 動画IDの抽出
        video_id = video_url.split("v=")[1].split("&")[0]
        try:
            # ライブチャットIDの取得
            live_chat_id = self._get_live_chat_id(video_id)
            next_page_token = None
            print("ライブチャットのモニタリングを開始します...")
            while self.is_monitoring:
                try:
                    # メッセージの取得
                    chat_response = self._get_live_chat_messages(
                        live_chat_id, next_page_token
                    )
                    # 新しいメッセージの処理
                    for message in chat_response.get('items', []):
                        message_id = message['id']
                        # 未処理のメッセージのみを処理
                        if message_id not in self.processed_messages:
                            # messageのkeyを表示
                            author = message['authorDetails']['displayName']
                            text = message['snippet']['displayMessage']
                            # コメントをスレッドセーフなキューに追加
                            self.comments_manager.add_comment(author, text)
                            # Unityにメッセージを送信
                            # print(f"Comment: {author}: {text}")
                            self.server.send_message_to_all(
                                reply=text, action="Comment", emotion=author
                            )
                            # コールバック関数が指定されている場合は実行
                            if message_callback:
                                message_callback(author, text)
                            self.processed_messages.add(message_id)
                    # 古いメッセージIDを削除（最新の1000件のみ保持）
                    if len(self.processed_messages) > 1000:
                        self.processed_messages = set(
                            list(self.processed_messages)[-1000:]
                        )
                    # 次のページトークンの更新
                    next_page_token = chat_response.get('nextPageToken')
                    # ポーリング間隔（YouTube APIの制限を考慮）
                    time.sleep(10)
                except HttpError as e:
                    if e.resp.status in [403, 429]:  # レート制限エラー
                        print("レート制限に達しました。60秒待機します...")
                        time.sleep(60)
                        continue
                    else:
                        raise
        except KeyboardInterrupt:
            print("\nモニタリングを終了します。")
        except Exception as e:
            print(f"予期せぬエラーが発生しました: {e}")
            raise

    def start_monitoring(
        self, video_url: str, message_callback: Any = None
    ) -> threading.Thread | None:
        """コメント監視を開始する"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            print("既にモニタリングが実行中です。")
            return None

        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_live_chat,
            args=(video_url, message_callback),
            daemon=True,
        )
        self.monitoring_thread.start()
        return self.monitoring_thread

    def stop_monitoring(self) -> None:
        """コメント監視を停止する"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
            print("モニタリングを停止しました。")

    def get_random_comment(self) -> dict | None:
        """ランダムなコメントを取得する"""
        return self.comments_manager.get_random_comment()
