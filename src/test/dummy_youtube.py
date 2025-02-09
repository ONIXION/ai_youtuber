from collections import deque
import random

class DummyYouTubeLiveChat:
    def __init__(self) -> None:
        self.comments: deque[dict] = deque(maxlen=1000)

    def start_monitoring(self) -> None:
        while True:
            comment = input("Please input a comment or 'exit' to quit: ")
            if comment == "exit":
                break
            author = "社会の歯車"
            self.comments.append({'author': author, 'text': comment})

    def add_dummy_comment(self, comment: str) -> None:
        self.comments.append({"author": "dummy", "text": comment})

    def get_random_comment(self) -> dict | None:
        if not self.comments:
            return None
        # ランダムなindexを選択
        random_index = random.randint(0, len(self.comments) - 1)
        comment = self.comments[random_index]
        # random_indexより前のコメントを削除
        self.comments = deque(
            list(self.comments)[random_index + 1 :], maxlen=self.comments.maxlen
        )
        return comment