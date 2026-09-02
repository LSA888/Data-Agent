import asyncio
from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer

from app.conf.app_config import EmbeddingConfig, app_config
from app.core.log import logger


class LocalEmbeddingClient:
    """本地 sentence-transformers 嵌入客户端，绕过 TEI 容器。"""

    def __init__(self, model_path: str | Path, device: str = "cpu"):
        self.model_path = Path(model_path)
        self.device = device
        self._model: Optional[SentenceTransformer] = None

    def init(self):
        logger.info(f"加载本地 embedding 模型: {self.model_path}")
        self._model = SentenceTransformer(str(self.model_path), device=self.device)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError("Embedding model not initialized")
        embeddings = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
        )
        return embeddings.tolist()

    async def aembed_query(self, text: str) -> list[float]:
        embeddings = await self.aembed_documents([text])
        return embeddings[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError("Embedding model not initialized")
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.client: Optional[LocalEmbeddingClient] = None
        self.config = config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        # 优先使用本地 sentence-transformers 模型（项目 docker/embedding 目录）
        # 避免依赖不稳定的 TEI 容器
        project_root = Path(__file__).parents[2]
        model_path = project_root / "docker" / "embedding" / "bge-large-zh-v1.5"
        if model_path.exists():
            self.client = LocalEmbeddingClient(model_path=model_path, device="cpu")
            self.client.init()
        else:
            logger.warning(
                f"本地模型不存在: {model_path}，回退到 TEI/OpenAI 兼容接口"
            )
            from langchain_openai import OpenAIEmbeddings

            self.client = OpenAIEmbeddings(
                model="bge-large-zh-v1.5",
                base_url=f"{self._get_url()}/v1",
                api_key="dummy",
            )


embedding_client_manager = EmbeddingClientManager(app_config.embedding)
