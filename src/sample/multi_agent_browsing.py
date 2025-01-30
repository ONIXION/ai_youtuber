import asyncio
import subprocess
import time

import requests
from browser_use import Agent, Browser, BrowserConfig, Controller
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from langchain_openai import ChatOpenAI

# 例: Windows環境でのChrome実行ファイルパス
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


async def main(agent: Agent, browser: Browser) -> None:
    await agent.run()

    await browser.close()


if __name__ == '__main__':
    portA = 9222
    portB = 9223

    procA = start_chrome(portA, "C:/temp/chrome_profile_A")
    procB = start_chrome(portB, "C:/temp/chrome_profile_B")

    # 起動待ち
    time.sleep(3)

    browser1 = Browser(config=BrowserConfig(cdp_url=get_devtools_url(portA)))
    browser2 = Browser(config=BrowserConfig(cdp_url=get_devtools_url(portB)))

    config = BrowserContextConfig(
        browser_window_size={'width': 300, 'height': 400},
    )
    context1 = BrowserContext(browser=browser1, config=config)
    context2 = BrowserContext(browser=browser2, config=config)

    # Create the agent with your configured browser
    agent1 = Agent(
        task="Nvidiaの最新GPUについて教えて",
        llm=ChatOpenAI(model='gpt-4o'),
        browser_context=context1,
    )

    agent2 = Agent(
        task="AMDの最新GPUについて教えて",
        llm=ChatOpenAI(model='gpt-4o'),
        browser_context=context2,
    )

    async def _main() -> None:
        asyncio.gather(
            main(agent1, browser1),
            main(agent2, browser2),
        )

    asyncio.run(_main())
