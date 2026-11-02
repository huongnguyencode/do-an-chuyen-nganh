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
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0)
    db_pool_recycle_seconds: float = Field(default=1_800, gt=0)

    judge0_base_url: str = "http://localhost:2358"
    judge0_language_id: int | None = None
    judge0_auth_token: str | None = None
    judge0_auth_user: str | None = None
    judge0_poll_interval_seconds: float = Field(default=0.5, gt=0)
    judge0_poll_timeout_seconds: float = Field(default=15.0, gt=0)
    judge0_cpu_time_limit_seconds: float = Field(default=5.0, gt=0)
    judge0_wall_time_limit_seconds: float = Field(default=10.0, gt=0)
    judge0_memory_limit_kb: int = Field(default=256_000, gt=0)
    judge0_max_file_size_kb: int = Field(default=1_024, gt=0)
    grading_stale_run_timeout_seconds: int = Field(default=180, ge=30, le=3_600)

    # Cấu hình Hạn mức & Gợi ý sư phạm KM/KH (Chương 2 - Mục 2.2, 2.4, 2.5)
    # Ràng buộc le=3 đồng bộ với CheckConstraint(used_count <= 3) của bảng help_quota.
    hint_max_quota: int = Field(default=3, ge=1, le=3)
    hint_cooldown_seconds: int = Field(default=120, ge=0)
    hint_request_expire_seconds: int = Field(default=60, gt=0)
    hint_max_evidence: int = Field(default=2, ge=1, le=10)
    hint_max_retries: int = Field(default=2, ge=0, le=5)
    hint_allow_hidden_only: bool = True

    # Cấu hình Chiến lược LLM lai (Adapter Pattern: APIDemoAdapter & ColabQwenAdapter)
    llm_mode: Literal["api_demo", "colab_qwen", "fake", "disabled"] = "api_demo"
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model_id: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=15.0, gt=0)
    llm_max_tokens: int = Field(default=400, ge=50, le=2000)
    colab_qwen_model_id: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    colab_qwen_endpoint_url: str | None = None
    colab_qwen_api_key: str | None = None
    guardrail_token_overlap_threshold: float = Field(default=0.75, gt=0.0, le=1.0)

    @field_validator("judge0_language_id", mode="before")
    @classmethod
    def empty_language_id_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
