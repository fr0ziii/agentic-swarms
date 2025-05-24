# config/database.py
import os
from supabase import create_client
import openai
from dotenv import load_dotenv

load_dotenv()

# Configuración
supabase = create_client(
    os.getenv('SUPABASE_URL'), 
    os.getenv('SUPABASE_ANON_KEY')
)
openai.api_key = os.getenv('OPENAI_API_KEY')

def store_memory(agent_id: str, content: str, metadata: dict = None):
    """Almacena memoria con embedding en Supabase"""
    embedding = openai.embeddings.create(
        input=content, 
        model="text-embedding-3-small"
    ).data[0].embedding
    
    result = supabase.table('agent_memory').insert({
        'agent_id': agent_id,
        'content': content,
        'embedding': embedding,
        'metadata': metadata or {}
    }).execute()
    
    return result.data[0]['id']

def retrieve_memory(agent_id: str, query: str, limit: int = 5):
    """Recupera memoria relevante por similitud"""
    query_embedding = openai.embeddings.create(
        input=query,
        model="text-embedding-3-small"
    ).data[0].embedding
    
    result = supabase.rpc('match_memories', {
        'agent_id': agent_id,
        'query_embedding': query_embedding,
        'match_threshold': 0.7,
        'match_count': limit
    }).execute()
    
    return result.data