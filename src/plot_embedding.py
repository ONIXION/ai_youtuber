import logging
from logging import Formatter, StreamHandler, getLogger
from typing import List

import chromadb
import japanize_matplotlib
import matplotlib.pyplot as plt
import numpy as np
import torch
import umap
from langchain_core.runnables import Runnable, RunnableConfig, RunnableSequence
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

# ログの設定
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(handler_format)
logger.addHandler(stream_handler)


# 過去の埋め込みを保持するための簡易クラス
class EmbeddingMemory:
    def __init__(self) -> None:
        self.embeddings: List[List[float]] = []
        self.texts: List[str] = []

    def add_embeddings(self, new_embeddings: List[List[float]]) -> None:
        self.embeddings.extend(new_embeddings)

    def get_embeddings(self) -> List[List[float]]:
        return self.embeddings

    def add_texts(self, new_texts: List[str]) -> None:
        self.texts.extend(new_texts)

    def get_texts(self) -> List[str]:
        return self.texts


# 過去の埋め込みと新しい埋め込みを結合するRunnable
class MergeEmbeddingsRunnable(Runnable[List[List[float]], List[List[float]]]):
    def __init__(self, memory: EmbeddingMemory) -> None:
        super().__init__()
        self.memory = memory

    def invoke(
        self, new_embeddings: List[List[float]], config: RunnableConfig = None
    ) -> List[List[float]]:
        # 過去の埋め込みを取得
        merged = self.memory.get_embeddings()

        # 新しい埋め込みをマージ
        merged.extend(new_embeddings)  # この操作は元のmemoryも変更する
        return merged


# 埋め込みモデルRunnable
class EmbeddingRunnable(Runnable[str, List[float]]):
    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={
                "model_kwargs": {
                    "torch_dtype": torch.float16,
                }
            },
        )

    def invoke(self, texts: List[str], config: RunnableConfig = None) -> List[float]:
        result = self.model.embed_documents(texts)  # (len(texts), 1024)

        assert isinstance(result, List)
        return result


# UMAPによる次元削減Runnable
class UmapReducer(Runnable[List[List[float]], np.ndarray]):
    def __init__(self) -> None:
        super().__init__()
        self.reducer = umap.UMAP(n_neighbors=2, min_dist=0.3, metric="cosine")

    def invoke(
        self, embeddings: List[List[float]], config: RunnableConfig = None
    ) -> np.ndarray:
        array_data = np.array(embeddings)
        result = self.reducer.fit_transform(array_data)

        assert isinstance(result, np.ndarray)
        return result


def plot_embeddings(embeddings_2d: np.ndarray, texts: List[str]) -> None:
    if embeddings_2d.size == 0:
        print("プロットするデータがありません。")
        return
    plt.figure(figsize=(8, 6))
    plt.scatter(embeddings_2d[:, 0], embeddings_2d[:, 1], c="blue")
    for i, txt in enumerate(texts):
        plt.annotate(txt, (embeddings_2d[i, 0], embeddings_2d[i, 1]))
    plt.title("UMAP projection")
    plt.show()


if __name__ == "__main__":
    # メモリを初期化し、サンプルデータを追加
    memory = EmbeddingMemory()
    sample_data = [
        "あなたが好きです",
        "あなたが嫌いです",
        "あなたのことを知りたい",
        "あなたのことを教えて",
        "あなたは誰ですか",
        "あなたは何者ですか",
    ]
    sample_embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3").embed_documents(
        sample_data
    )
    memory.add_embeddings(sample_embeddings)
    memory.add_texts(sample_data)
    logger.info("サンプルデータを追加しました")

    merge_runnable = MergeEmbeddingsRunnable(memory=memory)

    embedding_model_name = "BAAI/bge-m3"
    embedding_runnable = EmbeddingRunnable(model_name=embedding_model_name)
    reduce_runnable = UmapReducer()

    chain = RunnableSequence(
        first=embedding_runnable, middle=[merge_runnable], last=reduce_runnable
    )

    while True:
        text = input("文字列を入力してください ('exit' で終了): ")
        if text.strip().lower() == 'exit':
            print("終了します。")
            break

        result = chain.invoke([text])
        memory.add_texts([text])
        print("次元削減結果:", result)
        plot_embeddings(result, memory.get_texts())
