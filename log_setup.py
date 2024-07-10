import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

log = logging.getLogger()
log.setLevel(logging.getLevelNamesMapping()[LOG_LEVEL])
logging.getLogger("urllib3").setLevel(logging.ERROR)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
log.addHandler(handler)
