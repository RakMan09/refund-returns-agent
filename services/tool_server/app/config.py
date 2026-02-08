from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/refund_agent",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    evidence_storage_dir: str = Field(default="data/evidence", alias="EVIDENCE_STORAGE_DIR")
    approach_b_catalog_dir: str = Field(default="data/raw/product_catalog_images", alias="APPROACH_B_CATALOG_DIR")
    approach_b_anomaly_dir: str = Field(default="data/raw/anomaly_images", alias="APPROACH_B_ANOMALY_DIR")


settings = Settings()
