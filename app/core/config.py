from dotenv import load_dotenv
import os

load_dotenv()

POSTGRES_DATABASE_URL = os.getenv("POSTGRES_DATABASE_URL")
ORACLE_DATABASE_URL = os.getenv("ORACLE_DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
