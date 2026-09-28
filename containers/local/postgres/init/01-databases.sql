-- Corre una sola vez, cuando el volumen de Postgres está vacío (`make clean` para repetir).
-- Una base por dueño; en Cloud Run el agente usa Neon (mismo esquema, otra URL).
CREATE DATABASE sofia_agent;  -- AG: checkpointer + Store de LangGraph
CREATE DATABASE sofia_bank;   -- SIM: disputas, handoffs y auditoría de la API simulada
CREATE DATABASE langfuse;     -- OPS: Langfuse self-hosted (perfil `langfuse`)
