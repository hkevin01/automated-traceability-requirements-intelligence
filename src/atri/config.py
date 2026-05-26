from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "ATRI API"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Security ---
    auth_enabled: bool = False
    auth_default_user: str = "system"
    auth_default_roles: str = "admin,reviewer,analyst"
    auth_bearer_token: str = "change-me"
    secret_key: str = "change-me-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # --- Data stores ---
    review_store_path: str = "data/processed/reviews.json"
    review_history_store_path: str = "data/processed/review_history.jsonl"
    graph_store_path: str = "data/processed/trace_graph.json"
    graph_backend_uri: str = ""
    graph_backend_user: str = ""
    graph_backend_password: str = ""
    graph_backend_name: str = "neo4j"
    vector_index_path: str = "data/processed/vector_index.json"
    audit_store_path: str = "data/processed/audit_events.jsonl"
    ingestion_store_path: str = "data/processed/ingested_artifacts.jsonl"

    # --- Frontend ---
    frontend_api_base_url: str = "http://localhost:8000"
    frontend_title: str = "ATRI Dashboard"

    # --- AI providers (optional, not required for core functionality) ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o-mini"
    llm_rationale_enabled: bool = False
    llm_rationale_cache_path: str = "data/processed/llm_rationale_cache.json"

    # --- OIDC / SSO ---
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_jwks_uri: str = ""
    oidc_audience: str = ""

    # --- Multi-tenancy ---
    multi_tenant_enabled: bool = False
    default_tenant_id: str = "default"
    tenant_data_root: str = "data/tenants"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ATRI_",
        extra="ignore",
    )


settings = Settings()
