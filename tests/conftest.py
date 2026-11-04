import os
import shutil
import tempfile
from pathlib import Path


os.environ.update(
    {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "PAYMENT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "JWT_SECRET_KEY": "pytest-only-secret-not-for-services",
        "INTERNAL_API_KEY": "pytest-only-internal-key",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": "1",
        "SMTP_FROM_EMAIL": "pytest@example.test",
        "SMTP_STARTTLS": "false",
    }
)


def pytest_configure(config):
    if any(
        argument == "--basetemp" or argument.startswith("--basetemp=")
        for argument in config.invocation_params.args
    ):
        return
    temp_parent = Path(__file__).resolve().parents[1] / ".pytest_tmp"
    temp_parent.mkdir(exist_ok=True)
    test_temp = Path(tempfile.mkdtemp(prefix="pytest-run-", dir=temp_parent))
    config.option.basetemp = str(test_temp)
    config._ibanking_generated_basetemp = test_temp


def pytest_unconfigure(config):
    test_temp = getattr(config, "_ibanking_generated_basetemp", None)
    expected_parent = Path(__file__).resolve().parents[1] / ".pytest_tmp"
    if test_temp is not None and test_temp.parent == expected_parent and test_temp.is_dir():
        shutil.rmtree(test_temp)
