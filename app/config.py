from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Python Practice PoC"
    app_env: Literal["development", "test", "production"] = "development"
    demo_login_name: str = "demo"
    max_source_code_length: int = Field(default=20_000, ge=100, le=200_000)
    database_url: str = Field(
        default="postgresql+psycopg://python_poc:python_poc@localhost:5432/python_poc"
    )
    judge0_base_url: str = "http://localhost:2358"
    judge0_language_id: int | None = None
    judge0_auth_token: str | None = None
    judge0_auth_user: str | None = None
    judge0_poll_interval_seconds: float = Field(default=0.5, gt=0)
    judge0_poll_timeout_seconds: float = Field(default=15.0, gt=0)
    judge0_cpu_time_limit_seconds: float = Field(default=2.0, gt=0)
    judge0_wall_time_limit_seconds: float = Field(default=5.0, gt=0)
    judge0_memory_limit_kb: int = Field(default=128_000, gt=0)
    judge0_max_file_size_kb: int = Field(default=1_024, gt=0)

    @field_validator("judge0_language_id", mode="before")
    @classmethod
    def empty_language_id_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
