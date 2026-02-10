# Typing helpers:
# - AsyncIterator: type voor async generators (zoals lifespan)
# - Sequence: returntype voor "lijstachtige" resultaten
from collections.abc import AsyncIterator, Sequence

# asynccontextmanager maakt van een async generator een contextmanager
# (FastAPI gebruikt dit voor startup/shutdown hooks via 'lifespan')
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Query

# SQLModel is een laag bovenop SQLAlchemy:
# - SQLModel: base class voor je ORM model (én Pydantic model)
# - Field: beschrijft kolom-eigenschappen (primary_key, index, default, etc.)
# - Session: DB sessie/transaction scope
# - create_engine: maakt de DB-engine (connectieconfig)
# - select: query builder
from sqlmodel import Field, Session, SQLModel, create_engine, select

# settings komt uit config.py en leest env vars (POSTGRES_SERVER, etc.)
from config import settings


class Measurement(SQLModel, table=True):
    """
    Dit is een SQLModel "table model":
        - table=True betekent: maak hier een echte database tabel voor.
        - Zonder table=True is het alleen een (Pydantic) datamodel.
    """

    # id is optional bij het aanmaken (None), DB maakt 'm dan aan (autoincrement)
    # primary_key=True: dit is de primaire sleutel
    id: int | None = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    sensor: str = Field(index=True)
    value: float

    # lambda-functie zodat elke record een eigen datetime heeft, ipv de date-time bij opstarten
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MeasurementCreate(SQLModel):
    """
    Input schema zodat de user bijv. niet zelf een id mee kan sturen.
    """

    device_id: str
    sensor: str
    value: float
    ts: datetime | None = None


# Engine = het "hart" van SQLAlchemy/SQLModel:
# bevat connectiestring en pool settings.
# str(...) maakt van de PostgresDsn een string URL.
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def create_db_and_tables() -> None:
    """
    SQLModel.metadata bevat alle table definitions die je met SQLModel gemaakt hebt.
    create_all(...) maakt tabellen aan als ze nog niet bestaan.
    (Let op: dit doet géén migrations; het is simpel "create if missing".)
    """
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan runs bij startup voordat de app requests accepteert."""
    # Hier maak je dus tabellen aan (eenmalig).
    create_db_and_tables()
    # yield geeft controle terug aan FastAPI: "startup is klaar, serve requests".
    yield
    # Na yield zou je shutdown-cleanup kunnen doen (closing resources),
    # maar dat is hier niet nodig.


# FastAPI app met lifespan hook:
# hiermee wordt create_db_and_tables() automatisch bij startup uitgevoerd.
app = FastAPI(lifespan=lifespan)


# -------------------------
# API endpoints ("routes")
# -------------------------


# bijvoorbeeld: http://localhost:8001/
@app.get("/")
def hello() -> str:
    """Simpele health/test endpoint"""
    return "Hello, Docker-IOT-World!"


@app.post("/measurements/")
def create_measurement(payload: MeasurementCreate) -> Measurement:
    """
    Ontvangt een meting als JSON payload en slaat deze op in de database.

    De request body wordt door FastAPI gevalideerd en geparsed naar een
    `MeasurementCreate`-object (Pydantic/SQLModel). Dit object bevat alleen
    de velden die een client (bijv. een ESP32) mag aanleveren.

    Op basis van deze payload wordt een `Measurement` database-object aangemaakt
    en opgeslagen in PostgreSQL. Database-gegenereerde velden, zoals de primaire
    sleutel (`id`), worden na het committen teruggelezen en meegegeven in de response.

    :param payload: De gevalideerde meetdata afkomstig van de client.
    :type payload: MeasurementCreate
    :return: De opgeslagen meting inclusief database-gegenereerde velden.
    :rtype: Measurement
    """
    measurement = Measurement(
        device_id=payload.device_id,
        sensor=payload.sensor,
        value=payload.value,
        ts=payload.ts or datetime.now(UTC),
    )

    with Session(engine) as session:
        session.add(measurement)  # Voeg object toe aan sessie (nog niet persistent)
        session.commit()  # commit schrijft de insert naar de DB
        session.refresh(
            measurement
        )  # refresh haalt DB-gegenereerde velden op (zoals id)
        return measurement  # Return wordt door FastAPI als JSON teruggestuurd


@app.get("/measurements/")
def read_measurements(limit: int = Query(100, ge=1, le=1000)) -> Sequence[Measurement]:
    """
    Als je niets meegeeft: GET /measurements/ → max 100 records
    Wil je meer: GET /measurements/?limit=500
    ge=1 en le=1000 voorkomen per ongeluk “geef 1 miljoen rijen”

    :param limit: Description
    :type limit: int
    :return: Description
    :rtype: Sequence[Measurement]
    """
    with Session(engine) as session:
        measurements = session.exec(select(Measurement).limit(limit)).all()
        return measurements
