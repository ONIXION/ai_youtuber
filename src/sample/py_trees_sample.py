import random

import py_trees
import py_trees.behaviours
import py_trees.composites

shared_blackboard = py_trees.blackboard.Blackboard()
shared_blackboard.player_choice = ""
shared_blackboard.computer_choice = ""
shared_blackboard.play_again_status = py_trees.common.Status.SUCCESS


# アクションノードの定義
class GetPlayerChoice(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(GetPlayerChoice, self).__init__(name)

    def initialise(self):
        pass

    def update(self):
        choice = input("選択してください (rock, paper, scissors): ").lower()
        if choice not in ['rock', 'paper', 'scissors']:
            print("不正な選択です。もう一度やり直してください。")
            return py_trees.common.Status.FAILURE
        # Blackboardに選択を保存
        shared_blackboard.player_choice = choice
        return py_trees.common.Status.SUCCESS


class GetComputerChoice(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(GetComputerChoice, self).__init__(name)

    def initialise(self):
        pass

    def update(self):
        choice = random.choice(['rock', 'paper', 'scissors'])
        shared_blackboard.computer_choice = choice
        print(f"コンピューターの選択: {choice}")
        return py_trees.common.Status.SUCCESS


class CompareChoices(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(CompareChoices, self).__init__(name)

    def initialise(self):
        pass

    def update(self):
        player = shared_blackboard.player_choice
        computer = shared_blackboard.computer_choice

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

    def initialise(self):
        pass

    def update(self):
        cont = input("もう一度プレイしますか？ (y/n): ").lower()
        if cont == 'y':
            shared_blackboard.play_again_status = py_trees.common.Status.SUCCESS
            return py_trees.common.Status.SUCCESS
        else:
            print("ゲームを終了します。")
            shared_blackboard.play_again_status = py_trees.common.Status.FAILURE
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
    root = create_janken_tree()
    tree = py_trees.trees.BehaviourTree(root)
    tree.setup(timeout=15)

    while True:
        status = tree.tick()
        # PlayAgain ノードの結果によってループを継続するか決定
        play_again_status = shared_blackboard.play_again_status
        if play_again_status == py_trees.common.Status.FAILURE:
            break


if __name__ == "__main__":
    main()
