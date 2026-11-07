from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / '.env'), extra='ignore')
    app_env: str = 'development'
    secret_key: str = 'dev-secret-change-me'
    cookie_secure: bool = False
    # Exact external HTTPS origin when a tunnel rewrites the upstream Host header.
    public_origin: str = Field(default='', pattern=r'^(?:https://[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]+)?)?$')
    database_url: str = ''
    redis_url: str = ''
    ai_mock: bool = False
    openai_api_key: str = ''
    model_fast: str = 'gpt-4o-mini'
    model_deep: str = 'gpt-4o'
    stt_provider: Literal['openai'] = 'openai'
    stt_fallback_provider: Literal[''] = ''
    stt_model: str = 'gpt-4o-transcribe'
    tts_provider: Literal['elevenlabs'] = 'elevenlabs'
    elevenlabs_api_key: str = ''
    elevenlabs_voice_hr: str = ''
    elevenlabs_voice_user: str = ''
    elevenlabs_voice_manager: str = ''
    elevenlabs_model_prepared: str = 'eleven_multilingual_v2'
    elevenlabs_model_live: str = 'eleven_multilingual_v2'
    elevenlabs_output_format: Literal['mp3_22050_32', 'mp3_24000_48', 'mp3_44100_32', 'mp3_44100_64', 'mp3_44100_96', 'mp3_44100_128', 'mp3_44100_192'] = 'mp3_44100_128'
    elevenlabs_language_code: str = Field(default='', pattern=r'^(?:[a-z]{2})?$')
    tts_prepared_timeout_sec: float = Field(default=60, gt=0, le=300)
    tts_live_timeout_sec: float = Field(default=30, gt=0, le=300)
    tts_cache: bool = True
    retry_limit: int = Field(default=2, ge=0, le=10)
    max_sessions_per_hour: int = Field(default=5, ge=1, le=1000)
    max_followups_enabled: bool = True
    followups_demo: int = Field(default=1, ge=0, le=3)
    followups_short: int = Field(default=2, ge=0, le=5)
    followups_standard: int = Field(default=3, ge=0, le=7)
    respond_timeout_sec: float = Field(default=60, gt=0, le=300)
    answer_seconds_junior: int = Field(default=90, ge=10, le=300)
    answer_seconds_middle: int = Field(default=120, ge=10, le=300)
    answer_seconds_senior: int = Field(default=120, ge=10, le=300)
    answer_seconds_manager: int = Field(default=150, ge=10, le=300)

    @model_validator(mode='after')
    def validate_runtime(self):
        if self.ai_mock:
            raise ValueError('AI_MOCK must be false; tests inject provider dependencies.')
        if self.app_env == 'production' and (len(self.secret_key) < 32 or self.secret_key.startswith('dev-') or not self.cookie_secure):
            raise ValueError('Production requires a random SECRET_KEY (32+ characters) and COOKIE_SECURE=true.')
        return self

    @property
    def db_url(self):
        return self.database_url or f'sqlite+aiosqlite:///{ROOT / "data/dev.db"}'

    def answer_seconds_for(self, level):
        return getattr(self, f'answer_seconds_{level}')

    def followups_for(self, question_count):
        if not self.max_followups_enabled:
            return 0
        return {3: self.followups_demo, 5: self.followups_short, 7: self.followups_standard}[question_count]


settings = Settings()
