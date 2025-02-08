# python -m src.test.test_embedding

import pytest

from src.utils.embedding import EmbeddinEngine

test_data = [
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


def test_embedding() -> None:
    engine = EmbeddinEngine(test_data)
    engine.update("あなたは何を思っていますか")
    texts1 = engine.embedding_memory.get_texts()
    texts2 = engine.reduced_embedding_memory.get_texts()
    embeddings = engine.reduced_embedding_memory.get_embeddings()
    reduced_embeddings = engine.reduced_embedding_memory.get_embeddings()

    assert len(texts1) == len(texts2)
    assert len(texts1) == len(embeddings)
    assert len(texts1) == len(reduced_embeddings)


def console_test_embedding() -> None:
    engine = EmbeddinEngine(test_data)
    while True:
        text = input("テキストを入力してください: ")
        if text.strip().lower() == "exit":
            print("終了します。")
            break
        engine.update(text)

    texts1 = engine.embedding_memory.get_texts()
    texts2 = engine.reduced_embedding_memory.get_texts()
    embeddings = engine.reduced_embedding_memory.get_embeddings()
    reduced_embeddings = engine.reduced_embedding_memory.get_embeddings()

    assert len(texts1) == len(texts2)
    assert len(texts1) == len(embeddings)
    assert len(texts1) == len(reduced_embeddings)


if __name__ == "__main__":
    console_test_embedding()
    # pytest.main(["-v", "-s", "src/test/test_embedding.py"])
