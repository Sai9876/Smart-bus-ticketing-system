import os, pathlib
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).resolve().parent / ".env")

print("USER =", os.getenv("DB_USER"))
print("PASS =", os.getenv("DB_PASS"))
print("DB =", os.getenv("DB_NAME"))
