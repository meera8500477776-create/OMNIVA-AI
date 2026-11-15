from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OMNIVA AI API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_mode: Literal["real", "demo"] = "real"
    database_url: str = "sqlite:///./omniva.db"
    secret_key: SecretStr = SecretStr("")
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    reset_token_minutes: int = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    secure_cookies: bool | None = None
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    max_request_bytes: int = 1_000_000
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return [origin.rstrip("/") for origin in value]

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        secret = self.secret_key.get_secret_value()
        if not secret:
            raise ValueError("SECRET_KEY must be provided")
        if (
            self.access_token_minutes < 1
            or self.refresh_token_days < 1
            or self.reset_token_minutes < 1
        ):
            raise ValueError("Token lifetimes must be positive")
        if self.app_env == "production":
            secret = self.secret_key.get_secret_value()
            if len(secret) < 32 or secret.lower() in {"change-me", "changethis", "secret"}:
                raise ValueError(
                    "Production requires a strong SECRET_KEY of at least 32 characters"
                )
            if not (self.smtp_host and self.email_from):
                raise ValueError(
                    "Production requires SMTP_HOST and EMAIL_FROM for password recovery"
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production requires PostgreSQL")
            if self.secure_cookies is False:
                raise ValueError("Production cookies must be Secure")
            if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins):
                raise ValueError("Production CORS origins cannot be local development hosts")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is forbidden in production")
        return self

    @property
    def cookies_secure(self) -> bool:
        if self.secure_cookies is not None:
            return self.secure_cookies
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
