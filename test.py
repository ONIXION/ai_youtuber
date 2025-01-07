from dotenv import load_dotenv
load_dotenv()
import asyncio
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller
from browser_use.browser.browser import Browser, BrowserConfig
import win32gui

def move_resize(x: int, y: int, width: int, height: int, title: str="Google Chrome"):
    # titleを含むウィンドウハンドルを取得
    def enum_window_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(enum_window_callback, results)
    if not results:
        print(f"No window found")
        return
    for hwnd in results:
        print(f"move and resize window: {win32gui.GetWindowText(hwnd)}")
        win32gui.MoveWindow(hwnd, x, y, width, height, True)

browser = Browser(
	config=BrowserConfig(
		headless=False,
		chrome_instance_path="C:\Program Files\Google\Chrome\Application\chrome.exe",
	)
)
controller = Controller()

async def main():
    task = "現在のNvidiaの株価を教えて"
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task=task,
        llm=model,
        controller=controller,
        browser=browser,
    )
    move_resize(100, 100, 800, 600)
    await agent.run()
	# await browser.close() # Close the browser

    input('Press Enter to close...')


if __name__ == '__main__':
    asyncio.run(main())