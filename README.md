# Windows Desktop Automation
Комбинированный подход в автоматизации Windows-приложений: UI Automation (pywinauto) + распознавание изображений (PyAutoGUI/OpenCV). В репозитории:

- `UiAgent` — единая обёртка с явными ожиданиями, фокусом окна, кликом `click_input()` и фолбэком на поиск по картинке;
- `WhatsAppAgent` — пример Page Object для UWP‑клиента WhatsApp;
- тест `test_send_message.py` — минимальный сценарий отправки сообщения.
- 
## Требования
- Windows 10/11, рабочий стол (не headless)
- Python 3.11+
- Установленный WhatsApp из Microsoft Store (UWP)
- Windows SDK (для Inspect.exe) — опционально

## Установка
```bash
pip install -e .[dev]
