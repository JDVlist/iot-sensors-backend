# Typing helpers:
# - AsyncIterator: type voor async generators (zoals lifespan)
# - Sequence: returntype voor "lijstachtige" resultaten
from collections.abc import AsyncIterator, Sequence

# asynccontextmanager maakt van een async generator een contextmanager
# (FastAPI gebruikt dit voor startup/shutdown hooks via 'lifespan')
from contextlib import asynccontextmanager

from fastapi import FastAPI

# SQLModel is een laag bovenop SQLAlchemy:
# - SQLModel: base class voor je ORM model (én Pydantic model)
# - Field: beschrijft kolom-eigenschappen (primary_key, index, default, etc.)
# - Session: DB sessie/transaction scope
# - create_engine: maakt de DB-engine (connectieconfig)
# - select: query builder
from sqlmodel import Field, Session, SQLModel, create_engine, select

# settings komt uit config.py en leest env vars (POSTGRES_SERVER, etc.)
from config import settings


# Dit is een SQLModel "table model":
# - table=True betekent: maak hier een echte database tabel voor.
# - Zonder table=True is het alleen een (Pydantic) datamodel.
class Hero(SQLModel, table=True):
    # id is optional bij het aanmaken (None), DB maakt 'm dan aan (autoincrement)
    # primary_key=True: dit is de primaire sleutel
    id: int | None = Field(default=None, primary_key=True)

    # index=True: zet een DB index op deze kolom (sneller zoeken/filteren)
    name: str = Field(index=True)

    # secret_name is verplicht (geen default) en niet geïndexeerd
    secret_name: str

    # age is optioneel, en ook geïndexeerd
    age: int | None = Field(default=None, index=True)


# Engine = het "hart" van SQLAlchemy/SQLModel:
# bevat connectiestring en pool settings.
# str(...) maakt van de PostgresDsn een string URL.
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def create_db_and_tables() -> None:
    # SQLModel.metadata bevat alle table definitions die je met SQLModel gemaakt hebt.
    # create_all(...) maakt tabellen aan als ze nog niet bestaan.
    # (Let op: dit doet géén migrations; het is simpel "create if missing".)
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Lifespan runs bij startup voordat de app requests accepteert.
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


@app.get("/")
def hello() -> str:
    # Simpele health/test endpoint
    return "Hello, Docker-iot-World!"


@app.post("/heroes/")
def create_hero(hero: Hero) -> Hero:
    # FastAPI parse't JSON body naar een Hero instance (Pydantic/SQLModel)
    # Session(engine) opent een DB sessie (unit-of-work scope)
    with Session(engine) as session:
        # Voeg object toe aan sessie (nog niet persistent)
        session.add(hero)

        # commit schrijft de insert naar de DB
        session.commit()

        # refresh haalt DB-gegenereerde velden op (zoals id)
        session.refresh(hero)

        # Return wordt door FastAPI als JSON teruggestuurd
        return hero


@app.get("/heroes/")
def read_heroes() -> Sequence[Hero]:
    with Session(engine) as session:
        # select(Hero) bouwt "SELECT * FROM hero"
        # session.exec(...).all() haalt alle resultaten op als lijst
        heroes = session.exec(select(Hero)).all()
        return heroes
