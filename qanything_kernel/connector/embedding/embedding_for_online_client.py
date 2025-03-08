"""Wrapper around YouDao embedding models."""
from typing import List
from qanything_kernel.utils.custom_log import debug_logger, embed_logger
from qanything_kernel.utils.general_utils import get_time_async, get_time
from langchain_core.embeddings import Embeddings
from qanything_kernel.configs.model_config import LOCAL_EMBED_SERVICE_URL, LOCAL_RERANK_BATCH
import traceback
import aiohttp
import asyncio
import requests


def _process_query(query):
    return '\n'.join([line for line in query.split('\n') if
                      not line.strip().startswith('![figure]') and
                      not line.strip().startswith('![equation]')])


class YouDaoEmbeddings(Embeddings):
    def __init__(self, semaphore=None):
        self.model_version = 'local_v20240725'
        self.url = f"http://{LOCAL_EMBED_SERVICE_URL}/embedding"
        self.session = requests.Session()
        self._semaphore = semaphore
        self.expected_dim = 768
        super().__init__()

    async def _get_embedding_async(self, session, queries):
        """添加验证和错误处理"""
        try:
            data = {'texts': [_process_query(text) for text in queries]}  # 确保文本预处理
            async with session.post(self.url, json=data) as response:
                response.raise_for_status()
                embeddings = await response.json()

                # 验证返回的embeddings
                if not embeddings or not isinstance(embeddings, list):
                    raise ValueError("Invalid embedding response format")

                # 验证每个向量的维度
                for emb in embeddings:
                    if not isinstance(emb, list) or len(emb) != self.expected_dim:
                        raise ValueError(f"Invalid embedding dimension: expected {self.expected_dim}, got {len(emb) if isinstance(emb, list) else 'not a list'}")
                    if not all(isinstance(x, float) for x in emb):
                        raise ValueError("Embedding contains non-float values")

                return embeddings
        except Exception as e:
            embed_logger.error(f"Embedding error: {str(e)}, queries: {queries[:100]}...")
            raise

    @get_time_async
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        batch_size = LOCAL_RERANK_BATCH
        all_embeddings = []

        if self._semaphore is None:
            debug_logger.warning("No semaphore provided, concurrent requests might not be limited")

        async with self._semaphore if self._semaphore else asyncio.nullcontext():
            async with aiohttp.ClientSession() as session:
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i + batch_size]
                    try:
                        embeddings = await self._get_embedding_async(session, batch_texts)
                        all_embeddings.extend(embeddings)
                    except Exception as e:
                        embed_logger.error(f"Batch {i//batch_size + 1} failed: {str(e)}")
                        raise

        embed_logger.info(f'Embedded {len(all_embeddings)} texts successfully')
        return all_embeddings

    async def aembed_query(self, text: str) -> List[float]:
        return (await self.aembed_documents([text]))[0]

    def _get_embedding_sync(self, texts):
        data = {'texts': [_process_query(text) for text in texts]}
        try:
            response = self.session.post(self.url, json=data)
            response.raise_for_status()
            result = response.json()
            return result
        except Exception as e:
            debug_logger.error(f'sync embedding error: {traceback.format_exc()}')
            return None

    # @get_time
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._get_embedding_sync(texts)

    @get_time
    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        # return self._get_embedding([text])['embeddings'][0]
        return self._get_embedding_sync([text])[0]

    @property
    def embed_version(self):
        return self.model_version

# 使用示例
# async def main():
#     embedder = YouDaoEmbeddings()
#     query = "Your query here"
#     texts = ["text1", "text2"]  # 示例文本
#     embeddings = await embedder.aembed_documents(texts)
#     return embeddings

# if __name__ == '__main__':
#     embeddings = asyncio.run(main())
