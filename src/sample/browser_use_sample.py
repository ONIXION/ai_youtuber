import asyncio

from browser_use import Agent, Browser, BrowserConfig, Controller
from langchain_openai import ChatOpenAI

# Configure the browser to connect to your Chrome instance
browser = Browser(
    config=BrowserConfig(
        # Specify the path to your Chrome executable
        chrome_instance_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
)

# Create the agent with your configured browser
agent = Agent(
    task="Nvidiaの最新GPUについて教えて",
    llm=ChatOpenAI(model='gpt-4o'),
    browser=browser,
    controller=Controller(),
)


async def main():
    await agent.run()

    input('Press Enter to close the browser...')
    await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
