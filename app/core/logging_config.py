import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")


def setup_logging(log_file=LOG_FILE):
    """
    Configura o logging da aplicação.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

    return logging.getLogger("app")


logger = setup_logging()
