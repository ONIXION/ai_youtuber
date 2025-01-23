from dataclasses import dataclass
from typing import cast


@dataclass
class Debater:
    name: str
    argument: str
    score: float


class Debate:
    def __init__(self, update_policy: str = "default") -> None:
        self.debaters: list[Debater] = []
        self.update_policy: str = update_policy

    def init_new_debate(
        self, names: list[str], arguments: list[str] | None = None
    ) -> None:
        """新しいディベートを初期化する

        Args:
            names (list[str]): ディベーターの名前のリスト
            arguments (list[str] | None, optional): 各ディベーターの主張のリスト. Defaults to None.
        """
        self.debaters = []
        assert len(names) > 1, "ディベートには2人以上のディベーターが必要です"
        for name in names:
            self.debaters.append(Debater(name=name, argument="", score=0))
        if arguments is not None:
            assert len(names) == len(arguments), "namesとargumentsの長さが一致しません"
            for i, argument in enumerate(arguments):
                self.debaters[i].argument = argument

    def update(self, update_arg: list[str] | list[float]) -> None:
        """各ディベーターのスコアを更新する

        Args:
            update_arg (str): 更新に使うデータ
        """
        match self.update_policy:
            case "simple_update":
                assert isinstance(
                    update_arg, list
                ), "update_argはlist型である必要があります"
                assert len(update_arg) == len(
                    self.debaters
                ), "update_argの長さが不正です"
                assert all(
                    [isinstance(arg, float) for arg in update_arg]
                ), "update_argはfloat型のリストである必要があります"

                update_arg_casted = cast(
                    list[float], update_arg
                )  # 型チェックを通すためにキャスト
                self._simple_update(update_arg_casted)
            case _:
                pass

    # TODO: 引き分けの場合の処理を追加
    def judge_winner(self) -> str:
        """勝者を判定する

        Returns:
            str: 勝者の名前
        """
        return max(self.debaters, key=lambda x: x.score).name

    def get_current_status(self) -> list[Debater]:
        """現在のディベートの状況を取得する

        Returns:
            list[Debater]: ディベーターのリスト
        """
        return self.debaters

    def _simple_update(self, update_arg: list[float]) -> None:
        for i, debater in enumerate(self.debaters):
            debater.score += update_arg[i]

    def _embedding_based_update(self, update_arg: list[str]) -> None:
        pass
