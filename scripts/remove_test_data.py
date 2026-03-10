import os

from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader, PyPDFLoader
from chromadb.errors import NotFoundError

from app.utils.fingerprint_store import delete
from app.retrieval.vector_store.chroma_client import get_client
from app.utils.hashing import sha256_text

TEST_TEAM_ID = "team_integration_test"


def remove_test_data():
    file_path = "tests/integration/sample.txt"

    ext = os.path.splitext(file_path)[1].lower()
        
    if ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext == ".md":
        loader = UnstructuredMarkdownLoader(file_path)
    elif ext == ".pdf":
        loader = PyPDFLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
        
    documents = loader.load()  # list of Document
    full_text = "\n".join([doc.page_content for doc in documents])

    doc_hash = sha256_text(full_text)
    delete(doc_hash, team_id=TEST_TEAM_ID)
    chroma_client = get_client()
    collection_name = f"team_{TEST_TEAM_ID}"
    try:
        chroma_client.get_collection(name=collection_name)
    except NotFoundError as e:
        print("collection 不存在，无需删除")
    else:
        chroma_client.delete_collection(name=collection_name)
