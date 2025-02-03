# python -m src.test.test_youtube_live

import logging
from logging import Formatter, StreamHandler, getLogger

import pytest

from src.main import YoutubeLive

# ログの設定
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(handler_format)
logger.addHandler(stream_handler)


def test_youtube_live() -> None:
    # 初期化
    youtube_live = YoutubeLive(mode="test")
    try:
        # モニタリングを開始
        youtube_live.start()
    except KeyboardInterrupt:
        # Ctrl+Cが押された場合に終了処理を実行
        logger.info("終了コマンドを受信しました")
    finally:
        # デコンストラクタを呼び出すことで終了処理を実行
        del youtube_live
    assert True


if __name__ == "__main__":
    test_youtube_live()
    # pytest.main(["-v", "-s", "src/test/test_youtube_live.py"])
