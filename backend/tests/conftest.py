"""Keep test imports independent of local database credentials and .env files."""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-only-signing-key-not-for-deployment"
os.environ["LOG_TO_FILE"] = "false"
