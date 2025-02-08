import subprocess

import requests

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def start_chrome(
    port: int,
    user_data_dir: str,
) -> subprocess.Popen:
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
