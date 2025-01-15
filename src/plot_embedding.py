import matplotlib.pyplot as plt
import numpy as np
import torch
import umap
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

# Load the embedding model
embedding_model_name = "BAAI/bge-m3"
embedding_model = HuggingFaceEmbeddings(
    model_name=embedding_model_name,
    model_kwargs={'model_kwargs': {"torch_dtype": torch.float16}},
)
