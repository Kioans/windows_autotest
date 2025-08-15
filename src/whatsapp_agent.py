from dataclasses import dataclass
from datetime import datetime
from typing import Any
from io import StringIO
from contextlib import redirect_stdout

from src.ui_agent import UiAgent


# Locator — компактный контейнер для локатора.
# Датакласс хранит словарь параметров (auto_id, control_type, title_re и т. д.) и позволяет передавать их через **locator.
# Это делает описания элементов короткими и переиспользуемыми.
@dataclass(frozen=True)
class Locator:

    params: dict[str, Any]



    def __iter__(self):

        return iter(self.params.items())



# Часто используемые локаторы элементов вынесены в константы.
SEARCH_BOX = Locator({"auto_id": "SearchQueryTextBox", "control_type": "Edit"})

CHAT_TEXT_BOX = Locator({"auto_id": "InputBarTextBox", "control_type": "Edit"})

SENT_MSG_RE = Locator({

    "auto_id": "TextBlock",

    "control_type": "Text",

    "title_re": "{pattern}",

})

WHATSAPP_SENT_MSG_IMG_FOLDER = "whatsapp/attach_btn"



# __init__ — сохраняем ссылку на общий драйвер.
# Получаем готовый UiAgent, чтобы переиспользовать его базовые операции (клики, ввод, ожидания).
# В классе WhatsAppAgent будут описаны базовые методы, специфичные для этого приложения.
class WhatsAppAgent:



    def __init__(self, ui: UiAgent):

        self.ui = ui



    # dump_controls — выгружаем дерево UI в файл.
    # Позволяет разово «снять» структуру элементов и сохранить в файл whatsapp_controls_YYYY.MM.DD.HH-MM-SS.txt
    # — удобно для анализа локаторов. Метод позволяет отлаживать код поиска элементов по локаторам.
    def dump_controls(self) -> None:

        timestamp = datetime.now().strftime("%Y.%m.%d.%H-%M-%S")

        file_name = f"whatsapp_controls_{timestamp}.txt"



        buf = StringIO()

        with redirect_stdout(buf):

            self.ui.app.window().dump_tree(depth=None)



        with open(file_name, "w", encoding="utf-8") as f:

            f.write(buf.getvalue())



    # open_chat — открываем нужный чат через поиск.
    # Нажимаем Ctrl + F, ждём, пока фокус перейдёт в строку поиска.
    # Вводим имя контакта и жмём Enter — WhatsApp открывает диалог.
    def open_chat(self, name: str) -> None:

        self.ui.type_keys("^f")

        self.ui.wait_for_keyboard_focus(SEARCH_BOX.params)

        self.ui.type_keys(name, enter=True)



    # send_message — печатаем и отправляем сообщение.
    # Кликаем в поле ввода (если элемент не может быть найден по локатору, используем заранее подготовленную картинку).
    # Дожидаемся реального фокуса клавиатуры. Печатаем текст и отправляем Enter.
    def send_message(self, text: str) -> None:

        self.ui.click(CHAT_TEXT_BOX.params, fallback_img_folder=WHATSAPP_SENT_MSG_IMG_FOLDER)

        self.ui.wait_for_keyboard_focus(CHAT_TEXT_BOX.params)

        self.ui.type_keys(text, enter=True)
