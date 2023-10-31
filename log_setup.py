import logging
import os
import sys
from pathlib import Path
from time import sleep
from typing import Any, Callable, Tuple, Union

import undetected_chromedriver as uc
from dotenv import load_dotenv
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

log = logging.getLogger()
log.setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.ERROR)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
log.addHandler(handler)
