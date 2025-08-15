import logging
import subprocess
import re
from datetime import datetime

import pytest

from src.ui_agent import UiAgent
from src.whatsapp_agent import SENT_MSG_RE, WhatsAppAgent
from config import CONTACT_PHONE

logger = logging.getLogger(__name__)


@pytest.fixture
def whatsapp():
    app_name = "WhatsApp"
    pkg = (
        subprocess.run(
            [
                "powershell",
                f"Get-AppxPackage *{app_name}* | Select-Object -ExpandProperty PackageFamilyName",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        .stdout.strip()
        .decode("utf-8")
    )
    logger.info(pkg)
    ui = UiAgent()
    ui.connect(f"shell:AppsFolder\\{pkg}!App", title_re=app_name, timeout=25)
    ui.get_focus_on_window(title_re=app_name)
    wa = WhatsAppAgent(ui)
    yield wa
    ui.close()


def test_send_message(whatsapp):
    contact = CONTACT_PHONE
    message = f"Hello from pywinauto {datetime.now().strftime('%Y.%m.%d.%H-%M-%S')}"
    whatsapp.open_chat(contact)
    whatsapp.send_message(message)
    txt = re.escape(message).replace(r"\\ ", r"[ \\u00A0]")
    pattern = rf"^{txt}(?:\\r\\n)?\\u200e?$"
    whatsapp.ui.wait_for(
        {**SENT_MSG_RE.params, "title_re": pattern},
        timeout=10,
    )
