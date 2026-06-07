"""Environment-driven configuration — the single source of truth for settings."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    cassandra_hosts: str = "127.0.0.1"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "acme_dwh"
    cassandra_replication_factor: int = 1
    cassandra_local_dc: str = "datacenter1"
    cassandra_username: str | None = None
    cassandra_password: str | None = None

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_path: str = "/api"
    max_data_range_days: int = 370  # largest /data span served in one call

    ingest_provider: str = "bitfinex"  # "bitfinex" | "nasdaq_data_link"
    ndl_api_key: str | None = None

    mcp_api_base_url: str = "http://127.0.0.1:8000/api"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    # ---- Spark jobs launched on demand from the API (UI "Run pipeline") ----
    docker_bin: str = "docker"
    spark_container: str = "acme-spark"
    spark_submit_path: str = "/opt/spark/bin/spark-submit"
    spark_connector_package: str = "com.datastax.spark:spark-cassandra-connector_2.12:3.5.1"
    spark_cassandra_host: str = "cassandra"  # hostname as seen *inside* the docker network
    spark_job_timeout: int = 600  # seconds; first run may download the connector

    @property
    def cassandra_contact_points(self) -> list[str]:
        return [h.strip() for h in self.cassandra_hosts.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
