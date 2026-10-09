"""Test setup: every test run uses a throwaway SQLite file, never the real database."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="fieldverify-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
# Keep tests independent of whatever is in the developer's .env.
for var in ("DEMO_PROVIDER_FIRST", "DEMO_PROVIDER_LAST", "DEMO_PROVIDER_DOB"):
    os.environ[var] = ""
