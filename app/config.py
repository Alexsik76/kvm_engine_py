from pathlib import Path
from app.settings import Settings as NewSettings

class Settings(NewSettings):
    @classmethod
    def from_file(cls, path: Path = None) -> "Settings":
        return cls()
