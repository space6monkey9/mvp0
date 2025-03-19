from . import models
from sqlmodel import SQLModel, create_engine
import os

DB_URL = os.environ.get(db_url)
engine = create_engine(DB_URL)