"""Create an operator key in .env without printing or replacing a secret."""
from pathlib import Path
import os
import secrets

destination = Path(__file__).resolve().parent.parent / ".env"
try:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; preserved unchanged.")
with os.fdopen(descriptor, "w") as f:
    f.write(f"FRANKENFLY_CONTROL_TOKEN={secrets.token_urlsafe(36)}\n")
    f.write("FRANKENFLY_DOMAIN=localhost\nFRANKENFLY_HZ=8\n")
print("Created .env with a random operator key. Edit FRANKENFLY_DOMAIN before public hosting.")
