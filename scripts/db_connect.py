from app.retrieval.vector_store.chroma_client import get_client

if __name__ == "__main__":
    client = get_client()
    print(client.heartbeat())