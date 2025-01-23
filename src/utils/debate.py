from dataclasses import dataclass
from typing import cast

from src.utils.embedding import EmbeddinEngine


@dataclass
class Debater:
    name: str
    argument: str
    score: float


class Debate:
    def __init__(
        self,
        update_policy: str = "default",
        embeddin_engine: EmbeddinEngine | None = None,
    ) -> None:
        self.debaters: list[Debater] = []
        if update_policy not in ["simple_update", "embedding_based_update"]:
            raise ValueError(
                "update_policyは'simple_update'または'embedding_based_update'である必要があります"
            )
        self.update_policy: str = update_policy
        if update_policy == "embedding_based_update" and embeddin_engine is None:
            raise ValueError(
                "update_policyが'embedding_based_update'の場合、EmbeddingEngineが必要です"
            )
        self.embedding_engine: EmbeddinEngine = embeddin_engine

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

        if self.update_policy == "embedding_based_update":
            assert (
                arguments is not None
            ), "argumentsがNoneの場合、embedding_based_updateは使用できません"
            self.embedding_engine.clear()
            init_data = [
                self.debaters[0].argument,
                self.debaters[1].argument,
                f"{self.debaters[0].argument}は{self.debaters[1].argument}よりも正しい",
                f"{self.debaters[1].argument}は{self.debaters[0].argument}よりも正しい",
                "どちらも正しくない",
            ]
            self.embedding_engine.init_memory(init_data)

    def update(self, update_arg: str | list[float]) -> None:
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
            case "embedding_based_update":
                assert isinstance(
                    update_arg, str
                ), "update_argはstr型である必要があります"
                self._embedding_based_update(update_arg)
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

    def _embedding_based_update(self, update_arg: str) -> None:
        if self.embedding_engine is None:
            raise ValueError(
                "このupdate_policyにはEmbeddingEngineが必要ですが、EmbeddingEngineが設定されていません"
            )
        self.embedding_engine.update(update_arg)
        reduced_embeddings = (
            self.embedding_engine.reduced_embedding_memory.get_embeddings()
        )

        # reduced_embeddings[0], [1] をそれぞれ argument1, argument2 のベクトルと判断
        arg0_vec = reduced_embeddings[0]
        arg1_vec = reduced_embeddings[1]

        # 距離計算用の関数（ユークリッド距離の2乗で比較）
        def dist_sq(a: list[float], b: list[float]) -> float:
            return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

        # 各ディベーターに加算するスコアをカウント
        score_arg0 = 0
        score_arg1 = 0

        # 2番目以降の要素は観測点としてどちらに近いかを判定
        for i in range(2, len(reduced_embeddings)):
            point = reduced_embeddings[i]
            dist1 = dist_sq(arg0_vec, point)
            dist2 = dist_sq(arg1_vec, point)
            if dist1 < dist2:
                score_arg0 += 1
            else:
                score_arg1 += 1

        # ディベーター0番目がargument1を主張し、1番目がargument2を主張していると想定
        self.debaters[0].score += score_arg0
        self.debaters[1].score += score_arg1
