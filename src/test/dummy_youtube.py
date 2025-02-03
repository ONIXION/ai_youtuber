from collections import deque


class DummyYouTubeLiveChat:
    def __init__(self) -> None:
        self.comments: deque[dict] = deque(maxlen=1000)
        self.add_dummy_comment("蜜柑はりんごは蜜柑より甘いか")
        self.add_dummy_comment("蜜柑はりんごは蜜柑より甘いか")
        self.add_dummy_comment("蜜柑はりんごは蜜柑より甘い")
        self.add_dummy_comment("りんごは蜜柑より甘い")
        self.add_dummy_comment("蜜柑より甘い果物はない")
        self.add_dummy_comment("りんごより甘い果物はない")

    def start_monitoring(self) -> None:
        while True:
            comment = input("Please input a comment or 'exit' to quit: ")
            if comment == "exit":
                break
            author = "dummy"
            self.comments.append({'author': author, 'text': comment})

    def add_dummy_comment(self, comment: str) -> None:
        self.comments.append({"author": "dummy", "text": comment})

    def get_random_comment(self) -> dict | None:
        if not self.comments:
            return None
        res = self.comments.popleft()
        assert isinstance(res, dict)
        return res
