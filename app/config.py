from pydantic import DirectoryPath
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    mediamtx_path: DirectoryPath = "/home/alex/mediamtx"
    log_level: str = "INFO"