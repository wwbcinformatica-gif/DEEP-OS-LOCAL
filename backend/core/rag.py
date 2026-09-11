import json
import logging

logger = logging.getLogger(__name__)

_embeddings = None
_vectorstore = None
_retriever = None

def _lazy_init():
    global _embeddings, _vectorstore, _retriever
    if _embeddings is not None:
        return True
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        return True
    except Exception as e:
        logger.warning(f"Embeddings not available: {e}")
        _embeddings = False
        return False

def build_vectorstore(faq_path):
    global _vectorstore, _retriever
    if not _lazy_init():
        return
    try:
        from langchain_community.vectorstores import FAISS
        with open(faq_path, encoding="utf-8") as f:
            docs = json.load(f)
        texts = [doc.get("texto", "") for doc in docs if doc.get("texto")]
        if not texts:
            texts = ["Nenhum conhecimento cadastrado."]
        _vectorstore = FAISS.from_texts(texts, _embeddings)
        _retriever = _vectorstore.as_retriever(search_kwargs={"k": 6})
    except Exception as e:
        logger.warning(f"Failed to build vectorstore: {e}")

def rebuild_vectorstore(faq_path):
    build_vectorstore(faq_path)

def get_rag_context(question: str) -> str:
    if _retriever is None:
        return ""
    try:
        docs = _retriever.invoke(question)
        return "\n".join([d.page_content for d in docs]) if docs else ""
    except Exception as e:
        logger.warning(f"RAG query failed: {e}")
        return ""
