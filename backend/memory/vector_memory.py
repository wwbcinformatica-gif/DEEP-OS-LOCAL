import json
import logging
from datetime import datetime

from core.config import MEMORY_DIR

logger = logging.getLogger(__name__)

VECTOR_MEMORY_DIR = MEMORY_DIR / "vectors"
VECTOR_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

_embeddings = None
_indexes = {}

def _lazy_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        return _embeddings
    except Exception as e:
        logger.warning(f"Embeddings unavailable: {e}")
        _embeddings = False
        return None

def _get_faiss():
    try:
        from langchain_community.vectorstores import FAISS
        return FAISS
    except ImportError:
        return None

def _get_index(namespace: str):
    if namespace in _indexes:
        return _indexes[namespace]
    emb = _lazy_embeddings()
    faiss = _get_faiss()
    if not emb or not faiss:
        return None
    index_path = VECTOR_MEMORY_DIR / f"{namespace}.faiss"
    try:
        if index_path.exists():
            _indexes[namespace] = faiss.load_local(
                str(index_path), emb, allow_dangerous_deserialization=True
            )
        else:
            _indexes[namespace] = faiss.from_texts(
                ["Inicializando memória vetorial..."], emb
            )
    except Exception as e:
        logger.warning(f"Failed to load FAISS index {namespace}: {e}")
        return None
    return _indexes[namespace]

def _save_index(namespace: str, index):
    if index is None:
        return
    index_path = VECTOR_MEMORY_DIR / f"{namespace}.faiss"
    try:
        index.save_local(str(index_path))
    except Exception as e:
        logger.warning(f"Failed to save FAISS index {namespace}: {e}")

async def vector_memory_add(namespace: str, text: str, metadata: dict = None):
    index = _get_index(namespace)
    if index is None:
        return
    meta_str = json.dumps(metadata or {}, ensure_ascii=False)
    index.add_texts([text], metadatas=[{"text": text, "meta": meta_str, "timestamp": datetime.now().isoformat()}])
    _save_index(namespace, index)

async def vector_memory_search(namespace: str, query: str, k: int = 5) -> list:
    index = _get_index(namespace)
    if index is None:
        return []
    try:
        docs = index.similarity_search(query, k=k)
        results = []
        for d in docs:
            results.append({
                "content": d.page_content[:300],
                "metadata": d.metadata if hasattr(d, "metadata") else {},
            })
        return results
    except Exception as e:
        logger.warning(f"Vector search failed: {e}")
        return []

def list_vector_namespaces() -> list:
    return [f.stem for f in VECTOR_MEMORY_DIR.glob("*.faiss")]

async def vector_memory_delete(namespace: str):
    index_path = VECTOR_MEMORY_DIR / f"{namespace}.faiss"
    if index_path.exists():
        index_path.unlink()
    if namespace in _indexes:
        del _indexes[namespace]
    return True
