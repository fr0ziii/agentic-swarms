# test_memory.py
from config.database import store_memory, retrieve_memory

# Almacenar
memory_id = store_memory("lead_agent", "Cliente potencial: empresa SaaS 50 empleados, VP Marketing")

# Recuperar  
results = retrieve_memory("lead_agent", "empresa software marketing")
print(results)