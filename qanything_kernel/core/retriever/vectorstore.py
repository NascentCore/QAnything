from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional, List, Any, Iterable, Callable
from qanything_kernel.utils.custom_log import debug_logger, insert_logger
from qanything_kernel.configs.model_config import MILVUS_PORT, MILVUS_COLLECTION_NAME, MILVUS_HOST_LOCAL, EMBEDDING_CONCURRENCY
from qanything_kernel.connector.embedding.embedding_for_online_client import YouDaoEmbeddings
from qanything_kernel.utils.general_utils import get_time, get_time_async
from langchain_community.vectorstores.milvus import Milvus
from pymilvus.orm.collection import MutationResult, Collection
import asyncio
import time
from threading import local


class SelfMilvus(Milvus):
    def __init__(self, *args, semaphore=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_flush_time = 0
        self.inserted_since_last_flush = 0
        self.flush_interval = 600
        self.flush_threshold = 10000
        self.expected_dim = 768
        self.max_retries = 3
        self._semaphore = semaphore or asyncio.Semaphore(EMBEDDING_CONCURRENCY)  # 使用相同的配置
        self._batch_queue = asyncio.Queue()

    def _should_flush(self) -> bool:
        current_time = time.time()
        time_since_last_flush = current_time - self.last_flush_time
        return (self.inserted_since_last_flush >= self.flush_threshold or
                time_since_last_flush >= self.flush_interval or self.last_flush_time == 0)

    @get_time
    def _milvus_flush(self):
        asyncio.create_task(asyncio.to_thread(self.col.flush))
        self.last_flush_time = time.time()
        self.inserted_since_last_flush = 0
        insert_logger.info(f"Flushed Milvus collection at {self.last_flush_time}")

    def _create_collection(
            self, embeddings: list, metadatas: Optional[list[dict]] = None
    ) -> None:
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            MilvusException,
        )
        from pymilvus.orm.types import infer_dtype_bydata

        # Determine embedding dim
        dim = len(embeddings[0])
        fields = []
        if self._metadata_field is not None:
            fields.append(FieldSchema(self._metadata_field, DataType.JSON))
        else:
            # Determine metadata schema
            if metadatas:
                # Create FieldSchema for each entry in metadata.
                for key, value in metadatas[0].items():
                    print(key, value, flush=True)
                    # Infer the corresponding datatype of the metadata
                    dtype = infer_dtype_bydata(value)
                    # Datatype isn't compatible
                    if dtype == DataType.UNKNOWN or dtype == DataType.NONE:
                        debug_logger.error(
                            (
                                "Failure to create collection, "
                                "unrecognized dtype for key: %s"
                            ),
                            key,
                        )
                        raise ValueError(f"Unrecognized datatype for {key}.")
                    # Dataype is a string/varchar equivalent
                    elif dtype == DataType.VARCHAR:
                        fields.append(
                            FieldSchema(key, DataType.VARCHAR, max_length=65_535)
                        )
                    else:
                        fields.append(FieldSchema(key, dtype))

        # Create the text field
        fields.append(
            FieldSchema(self._text_field, DataType.VARCHAR, max_length=65_535)
        )
        # Create the primary key field
        if self.auto_id:
            fields.append(
                FieldSchema(
                    self._primary_field, DataType.INT64, is_primary=True, auto_id=True
                )
            )
        else:
            fields.append(
                FieldSchema(
                    self._primary_field,
                    DataType.VARCHAR,
                    is_primary=True,
                    auto_id=False,
                    max_length=65_535,
                )
            )
        # Create the vector field, supports binary or float vectors
        fields.append(
            FieldSchema(self._vector_field, infer_dtype_bydata(embeddings[0]), dim=dim)
        )

        # Create the schema for the collection
        schema = CollectionSchema(
            fields,
            description=self.collection_description,
            partition_key_field=self._partition_key_field,
        )

        # Create the collection
        try:
            self.col = Collection(
                name=self.collection_name,
                schema=schema,
                consistency_level=self.consistency_level,
                using=self.alias,
                num_partitions=64
            )
            # Set the collection properties if they exist
            if self.collection_properties is not None:
                self.col.set_properties(self.collection_properties)
        except MilvusException as e:
            debug_logger.error(
                "Failed to create collection: %s error: %s", self.collection_name, e
            )
            raise e

    def get_expr_result(self, expr: str, output_fields: List[str]) -> List[int] | None:
        """Get query result with expression

        Args:
            expr: Expression - E.g: "id in [1, 2]", or "title LIKE 'Abc%'"
            output_fields: List of fields to return

        Returns:
            List[int]: List of IDs (Primary Keys)
        """

        from pymilvus import MilvusException

        if self.col is None:
            debug_logger.debug("No existing collection to get pk.")
            return None

        try:
            query_result = self.col.query(
                expr=expr, output_fields=output_fields
            )
        except MilvusException as exc:
            debug_logger.error("Failed to get ids: %s error: %s", self.collection_name, exc)
            raise exc
        return query_result

    def _get_metadata_fields(self, metadatas: List[dict]) -> dict:
        """
        从metadata列表中提取字段和值
        """
        if not metadatas:
            return {}

        result = {}
        # 获取所有可用的字段名
        keys = (
            [x for x in self.fields if x != self._primary_field]
            if self.auto_id
            else [x for x in self.fields]
        )

        # 遍历每个metadata字典
        for key in keys:
            values = []
            for d in metadatas:
                if key in d:
                    values.append(d[key])
            if values:
                result[key] = values

        return result

    async def _process_batch(self, batch_texts, metadatas, timeout, batch_size, ids=None):
        """处理单个批次的文档"""
        async with self._semaphore:
            try:
                embeddings = await self.embedding_func.aembed_documents(batch_texts)

                # 验证embeddings
                if not embeddings or len(embeddings) != len(batch_texts):
                    raise ValueError(f"Embedding count mismatch: got {len(embeddings)}, expected {len(batch_texts)}")

                # 准备插入数据
                insert_dict = {
                    self._text_field: batch_texts,
                    self._vector_field: embeddings,
                }

                if not self.auto_id and ids:
                    insert_dict[self._primary_field] = ids

                # 添加metadata
                if metadatas:
                    if self._metadata_field is not None:
                        insert_dict[self._metadata_field] = metadatas
                    else:
                        metadata_fields = self._get_metadata_fields(metadatas)
                        insert_dict.update(metadata_fields)

                # 执行插入
                res = await asyncio.to_thread(self.col.insert,
                    [insert_dict[x] for x in self.fields if x in insert_dict],
                    timeout=timeout)

                return res.primary_keys

            except Exception as e:
                debug_logger.error(f"Batch processing failed: {str(e)}")
                raise

    async def aadd_texts(
            self,
            texts: Iterable[str],
            metadatas: Optional[List[dict]] = None,
            timeout: Optional[int] = None,
            batch_size: int = 1000,
            *,
            ids: Optional[List[str]] = None,
            **kwargs: Any,
    ) -> List[str]:
        """使用任务队列处理文档"""
        time_record = kwargs.get('time_record', {})
        texts = list(texts)
        pks = []

        # 初始化collection如果需要
        if not isinstance(self.col, Collection):
            init_embeddings = await self.embedding_func.aembed_documents(texts[:1])
            self._init(embeddings=init_embeddings, metadatas=metadatas[:1] if metadatas else None)

        # 创建批次任务
        tasks = []
        for i in range(0, len(texts), batch_size):
            end = min(i + batch_size, len(texts))
            batch_texts = texts[i:end]
            batch_ids = ids[i:end] if ids else None

            task = asyncio.create_task(
                self._process_batch(
                    batch_texts,
                    metadatas,
                    timeout,
                    batch_size,
                    batch_ids
                )
            )
            tasks.append(task)

        # 等待所有任务完成
        try:
            results = await asyncio.gather(*tasks)
            for batch_pks in results:
                pks.extend(batch_pks)
        except Exception as e:
            debug_logger.error(f"Document processing failed: {str(e)}")
            raise

        return pks


class VectorStoreMilvusClient:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.host = MILVUS_HOST_LOCAL
        self.port = MILVUS_PORT
        self._local_storage = local()
        self._semaphore = asyncio.Semaphore(EMBEDDING_CONCURRENCY)  # 使用相同的配置
        debug_logger.info(
            f'init vectorstore {self.host}, {MILVUS_COLLECTION_NAME}')

    @property
    def local_vectorstore(self) -> Milvus:
        """
        使用线程本地存储确保每个worker使用独立的实例
        """
        if not hasattr(self._local_storage, 'vectorstore'):
            self._local_storage.vectorstore = SelfMilvus(
                embedding_function=YouDaoEmbeddings(semaphore=self._semaphore),  # 传递信号量
                connection_args={"host": self.host, "port": self.port},
                collection_name=MILVUS_COLLECTION_NAME,
                partition_key_field="kb_id",
                auto_id=True,
                search_params={"params": {"ef": 64}},
                semaphore=self._semaphore  # 传递相同的信号量给SelfMilvus
            )
        return self._local_storage.vectorstore

    def get_local_chunks(self, expr, timeout=10):
        future = self.executor.submit(
            partial(self.local_vectorstore.get_pks, expr=expr, timeout=timeout))
        return future.result()

    # def delete_chunks(self, chunk_ids):
    #     res = self.vectorstore.delete(expr=f"chunk_id in {chunk_ids}")
    #     debug_logger.info(f'milvus delete chunk number: {len(chunk_ids)} res: {res}')

    @get_time
    def delete_expr(self, expr):
        # 如果expr为空，则不执行删除操作
        if len(self.get_local_chunks(expr)) == 0:
            debug_logger.info(f'expr: {expr} not found in local milvus')
            return
        try:
            res = self.local_vectorstore.delete(expr=expr, timeout=10)
            debug_logger.info(f'local milvus delete expr: {expr} res: {res}')
        except Exception as e:
            debug_logger.error(f'local milvus delete expr: {expr} error: {e}')
