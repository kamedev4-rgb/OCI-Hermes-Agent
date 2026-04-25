import os
from mem0 import Memory

def _get_config():
    password = os.environ.get("POSTGRES_PASSWORD", "jG0LJjpyVv")
    return {
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "intfloat/multilingual-e5-base",
                "embedding_dims": 768
            }
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "user": "myknot",
                "password": password,
                "host": "localhost",
                "port": 5432,
                "dbname": "myknot",
                "collection_name": "memories",
                "embedding_model_dims": 768
            }
        }
    }

def extract_and_save(user_id: str, messages: list) -> dict:
    mem = Memory.from_config(_get_config())
    result = mem.add(messages, user_id=user_id)
    return {"saved": len(result.get("results", [])), "user_id": user_id}

def search_memory(user_id: str, query: str, limit: int = 5) -> list:
    mem = Memory.from_config(_get_config())
    results = mem.search(query, user_id=user_id, limit=limit)
    return results.get("results", [])
