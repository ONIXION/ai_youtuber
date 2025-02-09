import os
import subprocess
import time

import requests  # type: ignore

CHROME_PATH = "/usr/bin/google-chrome"


def start_chrome(
    port: int,
    user_data_dir: str,
) -> subprocess.Popen:
    """
    指定ポートのDevTools Protocolを開放してChromeを起動。
    Xvfbを用いて仮想ディスプレイ上でChromeを起動します。
    ユーザーデータディレクトリも個別に指定するとセッションが干渉しにくくなります。
    """
    cmd = [
        "xvfb-run",
        "--auto-servernum",
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


def set_window_position_and_size(
    x: int, y: int, width: int, height: int, idx: int = -1
) -> bool:
    """Chromeウィンドウの位置とサイズを設定する

    Args:
        x: ウィンドウのX座標
        y: ウィンドウのY座標
        width: ウィンドウの幅
        height: ウィンドウの高さ
    """
    window_ids = (
        os.popen("xdotool search --onlyvisible --name 'Chrome'")
        .read()
        .strip()
        .split('\n')
    )
    if not window_ids:
        return False

    print(f"window_ids{window_ids}")

    window_id = window_ids[idx]
    os.system(f'xdotool windowsize {window_id} {width} {height}')
    os.system(f'xdotool windowmove {window_id} {x} {y}')
    return True


if __name__ == "__main__":
    # ポート番号を指定してChromeを起動
    portA = 9222
    portB = 9223
    procA = start_chrome(portA, "temp/chrome_profile_A")
    procB = start_chrome(portB, "temp/chrome_profile_B")

    # DevTools ProtocolのWebSocketエンドポイントを取得
    urlA = get_devtools_url(portA)
    urlB = get_devtools_url(portB)
    print(urlA)
    print(urlB)

    # Chromeのプロセスを終了
    procA.terminate()
    procB.terminate()

    # ps aux | grep chrome | awk '{print $2}' | xargs kill -9
    subprocess.run(["pkill", "-9", "chrome"])
