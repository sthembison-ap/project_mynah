#PLACEHOLDER FILE
#from pydantic import BaseSettings


# class Settings(BaseSettings):
#     database_url: str = "postgresql+psycopg2://user:pass@localhost:5432/dra"
#     # swap to your LLM provider as needed
#     llm_model: str = "gpt-4o-mini"
#     llm_temperature: float = 0.0
# 
#     class Config:
#         env_prefix = "DRA_"
# 
# 
# settings = Settings()


import os
from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()

class IBISConfig(BaseSettings):
    """IBIS API Configuration"""
    base_url: str = os.getenv("IBIS_BASE_URL", "")
    api_key: str = os.getenv("IBIS_API_KEY", "")
    user_id: str = os.getenv("IBIS_USER_ID", "")

    class Config:
        env_prefix = "IBIS_"

ibis_config = IBISConfig()