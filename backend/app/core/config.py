"""Application configuration loaded from environment / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # .../backend
DATA_DIR = BACKEND_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
DB_PATH = DATA_DIR / "udyammitra.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    # Default to a real, cheap model id. Override with OPENAI_MODEL for a
    # stronger narrative model (e.g. gpt-4o). gpt-5.4 is not a public id.
    openai_model: str = "gpt-4o-mini"
    openai_disabled: bool = False

    database_url: str = f"sqlite:///{DB_PATH.as_posix()}"

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ---- Alternate-data connectors (Problem Statement 3). All optional;
    # when unset, connectors raise NotImplementedError and the app falls back
    # to seeded/synthetic data. Wire real credentials via Secrets Manager.
    gsp_asp_base_url: str = ""          # GST via GSP/ASP partner
    gsp_asp_token: str = ""
    sahamati_aa_base_url: str = ""      # Account Aggregator gateway
    sahamati_aa_client_id: str = ""
    epfo_base_url: str = ""             # EPFO (scoped/gated)

    @property
    def offline_mode(self) -> bool:
        """Auto-enable offline mode if no key is configured."""
        return self.openai_disabled or not self.openai_api_key.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Sentinel value used in the CDK stack when DATABASE_URL should be composed from
# the Aurora credential secret (DB_SECRET) at runtime instead of being set
# directly. Lets the AWS deploy avoid hand-building a Postgres connection URL.
_DB_URL_SENTINEL = "postgresql+psycopg2://SET_AT_DEPLOY"


def _compose_db_url_from_secret(secret_arn: str) -> str | None:
    """Read an RDS credential secret (JSON) and build a psycopg2 URL.

    Returns None if the secret can't be read/parsed so the caller can fall back
    to the existing DATABASE_URL / SQLite default. Only invoked when DB_SECRET
    is set (AWS deploy); local dev never hits this path.
    """
    try:
        import boto3  # local import so dev installs without boto3
        import json as _json

        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "ap-south-1"
        client = boto3.client("secretsmanager", region_name=region)
        raw = client.get_secret_value(SecretId=secret_arn)["SecretString"]
        s = _json.loads(raw)
        user = s["username"]
        pwd = s["password"]
        host = s["host"]
        port = s.get("port", 5432)
        dbname = s.get("dbname") or "udyammitra"
        return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{dbname}"
    except Exception:
        return None


@lru_cache
def get_settings() -> Settings:
    # Also read from a root .env if present (developer convenience).
    root_env = BACKEND_DIR.parent / ".env"
    if root_env.exists():
        for line in root_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

    # AWS deploy: if DATABASE_URL is unset or the deploy sentinel, compose it
    # from the Aurora credential secret (DB_SECRET env = secret ARN, injected
    # by App Runner). Local dev leaves DB_SECRET unset → SQLite default stands.
    db_url = os.environ.get("DATABASE_URL", "")
    db_secret_arn = os.environ.get("DB_SECRET", "").strip()
    if db_secret_arn and (not db_url or db_url == _DB_URL_SENTINEL):
        composed = _compose_db_url_from_secret(db_secret_arn)
        if composed:
            os.environ["DATABASE_URL"] = composed

    return Settings()


settings = get_settings()