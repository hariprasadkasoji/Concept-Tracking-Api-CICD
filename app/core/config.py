from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Core App Settings
    SECRET_KEY: str = Field(..., alias="AUTH_SECRET_KEY")
    ALGORITHM: str = Field(..., alias="AUTH_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(..., alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # SQL Configs
    DB_DRIVER: str = Field(..., alias="DB_DRIVER")
    DB_HOST: str = Field(..., alias="DB_HOST")
    DB_USER: str = Field(..., alias="DB_USER")
    DB_PASSWORD: str = Field(..., alias="DB_PASSWORD")
    DB_NAME: str = Field(..., alias="DB_NAME")

    POOL_SIZE: int = 5
    DB_POOL_TIMEOUT:int = 10

    # Microsoft Auth
    MICROSOFT_CLIENT_ID: str | None = Field(default=None, validation_alias="MICROSOFT_CLIENT_ID")
    MICROSOFT_CLIENT_SECRET: str | None = Field(default=None, validation_alias="MICROSOFT_CLIENT_SECRET")
    MICROSOFT_TENANT_ID: str | None = Field(default=None, validation_alias="MICROSOFT_TENANT_ID")
    SESSION_SECRET: str | None = Field(default=None, validation_alias="MICROSOFT_SESSION_SECRET_KEY")

    # API / UI
    API: str | None = Field(default=None, validation_alias="API")
    UI_FRONTEND_URL: str | None = Field(default=None, validation_alias="UI_FRONTEND_URL")

    # Table Names
    USER_ROLE: str = "user_role"
    USERS: str = "users"
    USER_ACCESS: str = "user_access"
    CLIENTS: str = "clients"
    MASTER_CONCEPTS: str = "master_concepts"
    REVIEW_TYPE: str = "review_type"
    CLAIM_TYPE: str = "claim_type"
    DEVELOPMENT_STATUS: str = "development_status"
    PRIORITY_STATUS: str = "priority_status"
    CLIENT_APPROVAL_STATUS: str = "ClientApproval_status"
    CONCEPTS: str = "Concepts"
    CONCEPT_KEYS: str = "ConceptKeys"
    CONCEPT_DRAFTS: str = "ConceptDrafts"
    CLIENT_APPROVAL: str = "ClientApproval"
    CONCEPT_DEVELOPMENT_NOTES: str = "ConceptDevelopmentNotes"
    CONCEPT_ATTACHMENTS: str = "ConceptAttachments"

    # Environment and Storage Config
    ENVIRONMENT: str = Field(default="DEVELOPMENT", validation_alias="ENVIRONMENT")

    LOG_DIR: str | None = Field(
        default=None,
        validation_alias="LOG_DIR"
    )

    LOG_RETENTION_DAYS: int = Field(
        default=None,
        validation_alias="LOG_RETENTION_DAYS"
    )

    CONCEPT_FILES_DIR: str | None = Field(
        default=None,
        validation_alias="CONCEPT_FILES_DIR"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


# Singleton
settings = Settings()