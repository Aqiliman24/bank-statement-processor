from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # LLM Configuration
    llm_provider: str = "openai"  # "openai" or "lmstudio"
    openai_api_key: str # Not needed for LM Studio
    openai_model: str = "gpt-4.1-nano-2025-04-14"
    openai_base_url: str = "https://api.openai.com/v1"  # Override for LM Studio: http://localhost:1234/v1
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Upload
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
