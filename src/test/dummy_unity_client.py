import asyncio
import json

import websockets


async def dummy_client() -> None:
    uri = "ws://localhost:5000"  # サーバーのホストとポートは適宜変更してください
    try:
        async with websockets.connect(uri) as websocket:
            print("サーバーに接続しました。")

            # テストメッセージを送信
            test_message = {"message": "Hello from dummy client"}
            await websocket.send(json.dumps(test_message))
            print("送信メッセージ:", test_message)

            while True:
                # サーバーからのメッセージを待機する
                print("サーバーからのメッセージを待機中...")
                reply = await websocket.recv()
                # 受信した文字列をJSONとしてパース
                try:
                    data = json.loads(reply)
                    print("受信メッセージ:", data)
                except json.JSONDecodeError:
                    print("JSONのパースに失敗しました。受信内容:", reply)

                # 'Finish' メッセージを送信して終了
                finish_message = {"message": "Finish"}
                await websocket.send(json.dumps(finish_message, ensure_ascii=False))
                print("送信メッセージ:", finish_message)

                # 少し待ってから接続を閉じる
                await asyncio.sleep(1)

    except Exception as e:
        print(f"接続エラー: {e}")


if __name__ == "__main__":
    asyncio.run(dummy_client())
