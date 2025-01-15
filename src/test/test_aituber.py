# python -m src.test.test_aituber
import asyncio

import pytest

from src.ai_tuber import AItuber, TalkFormat, TalkInput


async def console_app() -> None:
    aituber = AItuber()
    while True:
        user_input = input("ユーザー: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("終了します...")
            break
        agent_input = TalkInput(name="初期設定", input=user_input).model_dump_json()
        response: dict = await aituber.graph.ainvoke({"messages": [agent_input]})
        response_content: TalkFormat = TalkFormat.model_validate_json(
            response['messages'][-1].content
        )
        print(f"AI: {response_content.reply}")
        print(f"AI: {response_content.emotion}")
        print(f"AI: {response_content.action}")


def test_console_app() -> None:
    asyncio.run(console_app())


if __name__ == "__main__":
    pytest.main(['-v', '-s', 'src/test/test_aituber.py'])
