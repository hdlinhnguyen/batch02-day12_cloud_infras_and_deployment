import os
import logging
from dataclasses import dataclass, field

@dataclass
class Settings:
    # Server configuration
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # FastAPI application metadata
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "AI Research Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "demo-key-change-in-production"))

    # Storage (Redis)
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Model Provider & Settings
    provider_name: str = field(default_factory=lambda: os.getenv("PROVIDER_NAME", "openrouter"))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "openai/gpt-4o-mini"))

    # Security Limits
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    monthly_budget_usd: float = field(default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0")))

    # Day 04 Model provider credentials
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    # Research / read tools keys
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    firecrawl_api_key: str = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))
    rapidapi_key: str = field(default_factory=lambda: os.getenv("RAPIDAPI_KEY", ""))
    rapidapi_twitter_host: str = field(default_factory=lambda: os.getenv("RAPIDAPI_TWITTER_HOST", "twitter-api45.p.rapidapi.com"))
    arxiv_user_agent: str = field(default_factory=lambda: os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0 (educational lab)"))

    def validate(self):
        """Perform validation and print startup warnings."""
        warnings = []
        if self.provider_name == "openrouter" and not self.openrouter_api_key:
            warnings.append("PROVIDER_NAME is 'openrouter' but OPENROUTER_API_KEY is not set!")
        elif self.provider_name == "openai" and not self.openai_api_key:
            warnings.append("PROVIDER_NAME is 'openai' but OPENAI_API_KEY is not set!")
        elif self.provider_name == "gemini" and not self.gemini_api_key:
            warnings.append("PROVIDER_NAME is 'gemini' but GEMINI_API_KEY is not set!")
        elif self.provider_name == "anthropic" and not self.anthropic_api_key:
            warnings.append("PROVIDER_NAME is 'anthropic' but ANTHROPIC_API_KEY is not set!")

        if self.agent_api_key == "demo-key-change-in-production" and self.environment == "production":
            raise ValueError("AGENT_API_KEY must be changed from default in production!")

        for w in warnings:
            logging.warning(w)
        return self

settings = Settings().validate()
