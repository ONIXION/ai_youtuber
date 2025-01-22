from dataclasses import dataclass
from typing import Callable

import py_trees


@dataclass
class AgentControllerContext:
    comment_store: str
    embedding_result_store: str
    embedding_conditon_callback: Callable[[None], None]


class AgentController:
    def __init__(self, context: AgentControllerContext):
        self.context = context
        blackboard = py_trees.blackboard.Client(name="AgentDialog")

    def run(self):
        pass

    def close(self):
        pass
