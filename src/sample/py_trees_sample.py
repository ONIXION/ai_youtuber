import random

import py_trees
import py_trees.behaviours
import py_trees.composites


# アクションノードの定義
class GetPlayerChoice(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(GetPlayerChoice, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(
            key="player_choice", access=py_trees.common.Access.WRITE
        )

    def initialise(self):
        pass

    def update(self):
        choice = input("選択してください (rock, paper, scissors): ").lower()
        if choice not in ['rock', 'paper', 'scissors']:
            print("不正な選択です。もう一度やり直してください。")
            return py_trees.common.Status.FAILURE
        # Blackboardに選択を保存
        self.blackboard.player_choice = choice
        return py_trees.common.Status.SUCCESS


class GetComputerChoice(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(GetComputerChoice, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(
            key="computer_choice", access=py_trees.common.Access.WRITE
        )

    def initialise(self):
        pass

    def update(self):
        choice = random.choice(['rock', 'paper', 'scissors'])
        self.blackboard.computer_choice = choice
        print(f"コンピューターの選択: {choice}")
        return py_trees.common.Status.SUCCESS


class CompareChoices(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(CompareChoices, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(
            key="player_choice", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="computer_choice", access=py_trees.common.Access.READ
        )

    def initialise(self):
        pass

    def update(self):
        player = self.blackboard.player_choice
        computer = self.blackboard.computer_choice

        if player == computer:
            print("引き分けです！")
        elif (
            (player == 'rock' and computer == 'scissors')
            or (player == 'paper' and computer == 'rock')
            or (player == 'scissors' and computer == 'paper')
        ):
            print("あなたの勝ちです！")
        else:
            print("コンピューターの勝ちです！")
        return py_trees.common.Status.SUCCESS


class PlayAgain(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(PlayAgain, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(
            key="play_again_status", access=py_trees.common.Access.WRITE
        )

    def initialise(self):
        pass

    def update(self):
        cont = input("もう一度プレイしますか？ (y/n): ").lower()
        if cont == 'y':
            self.blackboard.play_again_status = py_trees.common.Status.SUCCESS
            return py_trees.common.Status.SUCCESS
        else:
            print("ゲームを終了します。")
            self.blackboard.play_again_status = py_trees.common.Status.FAILURE
            return py_trees.common.Status.FAILURE


# 行動ツリーの構築
def create_janken_tree():
    root = py_trees.composites.Sequence("JankenSequence", memory=False)
    root.add_children(
        [
            GetPlayerChoice("GetPlayerChoice"),
            GetComputerChoice("GetComputerChoice"),
            CompareChoices("CompareChoices"),
            PlayAgain("PlayAgain"),
        ]
    )
    return root


# ツリーの実行
def main():
    # 行動ツリーの作成
    # py_trees.blackboard.Blackboard.enable_activity_stream(maximum_size=100)
    blackboard = py_trees.blackboard.Client(name="JankenBlackboard")
    # blackboard.register_key(key="player_choice", access=py_trees.common.Access.WRITE)
    # blackboard.player_choice = ""
    # blackboard.register_key(key="computer_choice", access=py_trees.common.Access.WRITE)
    # blackboard.computer_choice = ""
    blackboard.register_key(
        key="play_again_status", access=py_trees.common.Access.WRITE
    )
    blackboard.play_again_status = py_trees.common.Status.SUCCESS

    root = create_janken_tree()
    tree = py_trees.trees.BehaviourTree(root)
    tree.setup(timeout=15)

    while True:
        tree.tick()
        # PlayAgain ノードの結果によってループを継続するか決定
        play_again_status = blackboard.play_again_status
        if play_again_status == py_trees.common.Status.FAILURE:
            break


if __name__ == "__main__":
    main()
