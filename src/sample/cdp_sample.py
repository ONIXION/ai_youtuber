import subprocess
import time

import requests

# 例: Windows環境でのChrome実行ファイルパス
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def start_chrome(port: int, user_data_dir: str) -> subprocess.Popen:
    """
    指定ポートのDevTools Protocolを開放してChromeを起動。
    ユーザーデータディレクトリも個別に指定するとセッションが干渉しにくくなります。
    """
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def get_devtools_url(port: int) -> str:
    """
    DevTools ProtocolのWebSocketエンドポイント(例: ws://127.0.0.1:<port>/devtools/browser/<id>)を取得。
    """
    resp = requests.get(f"http://127.0.0.1:{port}/json/version")
    info = resp.json()
    url = info["webSocketDebuggerUrl"]  # DevTools Protocol用WebSocket URL
    assert isinstance(url, str)
    return url


if __name__ == "__main__":
    # 例として2つのChromeインスタンスを起動
    portA = 9222
    portB = 9223

    procA = start_chrome(portA, "C:/temp/chrome_profile_A")
    procB = start_chrome(portB, "C:/temp/chrome_profile_B")

    # 起動待ち
    time.sleep(3)

    # DevTools Protocol用WebSocket URLの確認
    ws_url_A = get_devtools_url(portA)
    ws_url_B = get_devtools_url(portB)

    print(f"Chrome A DevTools WebSocket URL: {ws_url_A}")
    print(f"Chrome B DevTools WebSocket URL: {ws_url_B}")

    # ここでws_url_A, ws_url_Bを使ってWebSocket通信し、各ブラウザを操作（ページ遷移、DOM操作など）できます。
    # 例: websocketsライブラリやplaywright、pyChromeDevToolsなどを利用

    input("エンターを押すと終了します...")

    # 終了処理
    procA.terminate()
    procB.terminate()
