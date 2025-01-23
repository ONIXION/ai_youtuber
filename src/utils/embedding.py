import logging
from logging import Formatter, StreamHandler, getLogger
from typing import Any, List

import hdbscan
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

japanize_matplotlib.japanize()  # flake8のエラーを出さないよう明示的に記述


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


class ReducedEmbeddingMemory:
    def __init__(self) -> None:
        self.embeddings: np.ndarray = np.array([])
        self.texts: List[str] = []

    def update_embeddings(self, new_embeddings: np.ndarray) -> None:
        self.embeddings = new_embeddings

    def get_embeddings(self) -> np.ndarray:
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


class EmbeddinEngine:
    def __init__(self, init_data: list[str] | None = None) -> None:
        if init_data is None:
            init_data = [
                "テストデータ1",
                "テストデータ2",
                "テストデータ3",
                "テストデータ4",
            ]
        # インタラクティブモードの有効化
        plt.ion()
        _, self.ax = plt.subplots(figsize=(10, 8))
        self.scatter = None
        self.chain: RunnableSequence | None = None
        self.embedding_memory: EmbeddingMemory | None = None
        self.reduced_embedding_memory: ReducedEmbeddingMemory | None = None

        self.init_memory(init_data)

    def init_memory(self, init_data: list[str]) -> None:
        # メモリを初期化
        self.embedding_memory = EmbeddingMemory()
        self.reduced_embedding_memory = ReducedEmbeddingMemory()

        # 初期データを追加
        init_embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3"
        ).embed_documents(init_data)
        self.embedding_memory.add_embeddings(init_embeddings)
        self.embedding_memory.add_texts(init_data)

        merge_runnable = MergeEmbeddingsRunnable(memory=self.embedding_memory)

        embedding_model_name = "BAAI/bge-m3"
        embedding_runnable = EmbeddingRunnable(model_name=embedding_model_name)
        reduce_runnable = UmapReducer()

        self.chain = RunnableSequence(
            first=embedding_runnable, middle=[merge_runnable], last=reduce_runnable
        )

        # 次元削減
        all_embeddings = self.embedding_memory.get_embeddings()
        all_texts = self.embedding_memory.get_texts()
        reduced_embeddings = reduce_runnable.invoke(all_embeddings)
        self.reduced_embedding_memory.update_embeddings(reduced_embeddings)
        self.reduced_embedding_memory.add_texts(all_texts)

        clusters = self._clusterring(reduced_embeddings)
        cluster_labels = self._get_cluster_labels(clusters, len(all_embeddings))
        self.scatter = self._plot_embeddings(
            reduced_embeddings, all_texts, self.ax, self.scatter, cluster_labels
        )

    def update(self, text: str) -> None:
        assert self.chain is not None
        assert self.embedding_memory is not None
        assert self.reduced_embedding_memory is not None

        result = self.chain.invoke([text])
        self.embedding_memory.add_texts([text])
        self.reduced_embedding_memory.add_texts([text])
        self.reduced_embedding_memory.update_embeddings(result)
        print("次元削減結果:", result)

        clusters = self._clusterring(result)
        cluster_labels = self._get_cluster_labels(clusters, len(result))

        self.scatter = self._plot_embeddings(
            result,
            self.embedding_memory.get_texts(),
            self.ax,
            self.scatter,
            cluster_labels,
        )

    def close(self) -> None:
        # インタラクティブモードのオフ
        plt.ioff()
        plt.show()

    def clear(self) -> None:
        self.embedding_memory = EmbeddingMemory()
        self.reduced_embedding_memory = ReducedEmbeddingMemory()
        merge_runnable = MergeEmbeddingsRunnable(memory=self.embedding_memory)

        embedding_model_name = "BAAI/bge-m3"
        embedding_runnable = EmbeddingRunnable(model_name=embedding_model_name)
        reduce_runnable = UmapReducer()

        self.chain = RunnableSequence(
            first=embedding_runnable, middle=[merge_runnable], last=reduce_runnable
        )
        self.scatter = None

    def _plot_embeddings(
        self,
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

    def _clusterring(self, embeddings: Any) -> List[List[int]]:
        clusterer = hdbscan.HDBSCAN(gen_min_span_tree=True, min_cluster_size=2)
        clusterer.fit(embeddings)

        # クラスタリングラベル[0, 1, 2, ...]をindexのリストに変換
        cluster_labels = clusterer.labels_
        cluster_num = len(set(cluster_labels))
        clusters: list = [[] for _ in range(cluster_num)]
        for index, label in enumerate(cluster_labels):
            clusters[label].append(index)

        logger.info(f"クラスタリング結果: {clusters}")
        return clusters

    def _get_cluster_labels(self, clusters: Any, data_len: int) -> List[int]:
        cluster_labels = [0] * data_len
        for cluster_id, cluster in enumerate(clusters):
            for index in cluster:
                cluster_labels[index] = cluster_id
        return cluster_labels
