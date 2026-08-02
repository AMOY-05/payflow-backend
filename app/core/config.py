from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "FintechPlatform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    REDIS_URL: str = "redis://localhost:6379/0"

    FX_SPREAD_PERCENT: float = 1.5
    EXCHANGE_RATE_API_KEY: str = ""

    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    AI_MODEL: str = "meta/llama-3.1-8b-instruct"
    AI_ENABLED: bool = True

    FLUTTERWAVE_PUBLIC_KEY: str = ""
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_ENCRYPTION_KEY: str = ""
    FLUTTERWAVE_BASE_URL: str = "https://api.flutterwave.com/v3"
    FLUTTERWAVE_WEBHOOK_SECRET: str = ""
    
    # Paystack
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PAYSTACK_WEBHOOK_SECRET: str = ""

    #BUDPAY
    BUDPAY_PUBLIC_KEY: str =""

    GREY_API_KEY: str = ""
    GREY_BASE_URL: str = "https://api.grey.co/v1"

    WISE_API_KEY: str = ""
    WISE_BASE_URL: str = "https://api.sandbox.wise.com"
    WISE_PROFILE_ID: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    WEBHOOK_BASE_URL: str = "https://your-domain.com"

    # Security
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20

    # Monitoring
    SENTRY_DSN: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # MongoDB (Admin Analytics)
    MONGODB_URL: str = ""
    MONGODB_DB_NAME: str = "payflow_admin"

    # Admin access
    ADMIN_SECRET_KEY: str = "12345tgfghjkoi76rfvbnju98uccvbhju8987fvh"

    # Email
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    # Frontend URL for email links
    FRONTEND_URL: str = "http://localhost:3000"

    # KYC
    KYC_UPLOAD_DIR: str = "uploads/kyc"
    KYC_MAX_FILE_SIZE_MB: int = 10

    # Resend API Key for email service
    RESEND_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()