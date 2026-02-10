import os
from typing import Any

# Pydantic types/validators:
# - PostgresDsn: type voor postgres connection strings
# - computed_field: computed property die ook onderdeel kan zijn van model output
# - field_validator: validator voor één field
# - model_validator: validator voor het hele model
from pydantic import (
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)

# MultiHostUrl is een helper om URLs op te bouwen (incl. user/pass/host/port/path)
from pydantic_core import MultiHostUrl

# BaseSettings leest settings uit environment variables (.env, docker env, etc.)
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Deze velden verwacht Pydantic Settings uit env vars:
    # In Docker Compose zet jij ze onder environment:
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str

    # Je mag password direct geven, of via file (Docker secrets pattern)
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_PASSWORD_FILE: str | None = None

    POSTGRES_DB: str

    @model_validator(mode="before")
    @classmethod
    def check_postgres_password(cls, data: Any) -> Any:
        """
        Checkt (voor veld-parsing) dat minstens één van:
        - POSTGRES_PASSWORD
        - POSTGRES_PASSWORD_FILE
        is gezet.

        Dit voorkomt dat je app start zonder DB credentials.
        """
        if isinstance(data, dict):
            password_file: str | None = data.get("POSTGRES_PASSWORD_FILE")  # type: ignore
            password: str | None = data.get("POSTGRES_PASSWORD")  # type: ignore
            if password_file is None and password is None:
                raise ValueError(
                    "At least one of POSTGRES_PASSWORD_FILE and POSTGRES_PASSWORD must be set."
                )
        return data  # type: ignore

    @field_validator("POSTGRES_PASSWORD_FILE", mode="before")
    @classmethod
    def read_password_from_file(cls, v: str | None) -> str | None:
        """
        Als POSTGRES_PASSWORD_FILE gezet is, lees dan het wachtwoord uit dat bestand.
        Dit past bij Docker secrets: /run/secrets/db-password
        """
        if v is not None:
            file_path = v
            if os.path.exists(file_path):
                with open(file_path) as file:
                    # strip() haalt newline eraf (secrets files eindigen vaak met newline)
                    return file.read().strip()
            raise ValueError(f"Password file {file_path} does not exist.")
        return v

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """
        Bouw de SQLAlchemy connection string op uit de settings.

        schema 'postgresql+psycopg' betekent:
        - PostgreSQL dialect
        - psycopg driver (psycopg3)
        """
        url = MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            # password: als POSTGRES_PASSWORD gevuld is, gebruik die
            # anders gebruik POSTGRES_PASSWORD_FILE (die door validator al is 'omgezet' naar echte password-string)
            password=self.POSTGRES_PASSWORD
            if self.POSTGRES_PASSWORD
            else self.POSTGRES_PASSWORD_FILE,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )
        return PostgresDsn(url)


# Dit maakt direct een Settings instance bij import.
# Effect: bij het importeren van config.py worden env vars meteen gelezen/geverifieerd.
settings = Settings()  # type: ignore
