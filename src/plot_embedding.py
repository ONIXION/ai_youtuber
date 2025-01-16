import logging
import warnings
from logging import Formatter, StreamHandler, getLogger
from typing import Any, List

import hdbscan
import japanize_matplotlib
import matplotlib.pyplot as plt
import numpy
import numpy as np
import torch
import umap
from langchain_core.runnables import Runnable, RunnableConfig, RunnableSequence
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from pyclustering.cluster.center_initializer import kmeans_plusplus_initializer
from pyclustering.cluster.gmeans import gmeans
from pyclustering.cluster.xmeans import xmeans

# ログの設定
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_format = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stream_handler = StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(handler_format)
logger.addHandler(stream_handler)

japanize_matplotlib.japanize()  # flake8のエラーを出さないよう明示的に記述
numpy.warnings = warnings  # type: ignore # pyclusteringのエラーを回避するための設定


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
        # [0,1]に正規化
        result = (result - result.min()) / (result.max() - result.min())

        assert isinstance(result, np.ndarray)
        return result


def plot_embeddings(
    embeddings_2d: np.ndarray,
    texts: List[str],
    ax: Any,
    scatter: Any,
    cluster_labels: List[int],
) -> Any:
    if embeddings_2d.size == 0:
        logger.warning("プロットするデータがありません。")
        return scatter
    ax.clear()
    scatter = ax.scatter(
        embeddings_2d[:, 0], embeddings_2d[:, 1], c=cluster_labels, cmap='viridis'
    )
    for i, txt in enumerate(texts):
        ax.annotate(txt, (embeddings_2d[i, 0], embeddings_2d[i, 1]))
    ax.set_title("UMAP projection with Clustering")
    plt.draw()
    plt.pause(0.001)  # 描画をリフレッシュ
    return scatter


def clusterring(embeddings: Any, cluster_num: int) -> List[List[int]]:
    # initial_centers = kmeans_plusplus_initializer(embeddings, cluster_num).initialize()
    # xmeans_instance = xmeans(embeddings, initial_centers, kmax=10)
    # xmeans_instance.process()
    # clusters = xmeans_instance.get_clusters()

    # logger.info(f"クラスタリング結果: {clusters}")
    # assert isinstance(clusters, List)
    # return clusters
    clusterer = hdbscan.HDBSCAN(gen_min_span_tree=True, min_cluster_size=2)
    clusterer.fit(embeddings)

    # クラスタリングラベル[0, 1, 2, ...]をindexのリストに変換
    cluster_labels = clusterer.labels_
    cluster_num = len(set(cluster_labels))
    clusters = [[] for _ in range(cluster_num)]
    for index, label in enumerate(cluster_labels):
        clusters[label].append(index)

    logger.info(f"クラスタリング結果: {clusters}")
    return clusters


def get_cluster_labels(clusters: Any, data_len: int) -> List[int]:
    cluster_labels = [0] * data_len
    for cluster_id, cluster in enumerate(clusters):
        for index in cluster:
            cluster_labels[index] = cluster_id
    return cluster_labels


if __name__ == "__main__":
    # インタラクティブモードの有効化
    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = None  # 初期化

    # メモリを初期化し、サンプルデータを追加
    memory = EmbeddingMemory()
    sample_data = [
        "あなたが好きです",
        "あなたが嫌いです",
        "あなたのことを知りたい",
        "あなたのことを教えて",
        "あなたは誰ですか",
        "あなたは何者ですか",
        "あなたはどこに住んでいますか",
        "あなたは何をしていますか",
        "あなたは何を食べますか",
        "あなたは何を飲みますか",
        "あなたは何を考えていますか",
        "あなたは何を知っていますか",
        "あなたは何を見ていますか",
        "あなたは何を聞いていますか",
        "あなたは何を話していますか",
        "あなたは何を感じていますか",
        "あなたは何を思っていますか",
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

    # 初回のプロット
    all_embeddings = memory.get_embeddings()
    all_texts = memory.get_texts()
    embeddings_2d = reduce_runnable.invoke(all_embeddings)
    clusters = clusterring(embeddings_2d, cluster_num=3)
    cluster_labels = get_cluster_labels(clusters, len(all_embeddings))
    scatter = plot_embeddings(embeddings_2d, all_texts, ax, scatter, cluster_labels)

    while True:
        text = input("文字列を入力してください ('exit' で終了): ")
        if text.strip().lower() == 'exit':
            print("終了します。")
            break

        result = chain.invoke([text])
        memory.add_texts([text])
        print("次元削減結果:", result)

        amount_centers = len(clusters)
        clusters = clusterring(result, amount_centers)
        cluster_labels = get_cluster_labels(clusters, len(result))

        scatter = plot_embeddings(
            result, memory.get_texts(), ax, scatter, cluster_labels
        )

    # インタラクティブモードのオフ
    plt.ioff()
    plt.show()
