# python -m src.test.unity_server_test

from src.connect_unity import WebSocketServer

if __name__ == "__main__":
    # サーバーのインスタンスを作成
    server = WebSocketServer(port=5000, debug=False)
    try:
        # サーバーを開始（別スレッドで実行）
        server.start()
        # メインスレッドでの操作例
        while True:
            message = input("Enter message to send (or 'quit' to exit): ")
            if message.lower() == 'quit':
                break
            server.send_message_to_all(
                name="server", reply=message, action="Test", emotion="normal", scene=""
            )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()
