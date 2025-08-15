"""Environment configuration loader."""

import os
from dotenv import load_dotenv

load_dotenv()

CONTACT_PHONE = os.getenv("CONTACT_PHONE")