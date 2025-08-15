import subprocess
from pathlib import Path
import logging
import os
from time import monotonic, sleep
from typing import Any, Mapping

from PIL import Image
import pyautogui
import pywinauto
import pywinauto.timings
from pywinauto import Desktop
from pywinauto.application import Application

logger = logging.getLogger(__name__)


class UiAgent:
    _CTYPES = ("Windows", "Pane", None)

    def __init__(self, backend: str = "uia") -> None:
        self.backend = backend
        self.app: Application | None = None
        self.main: pywinauto.base_wrapper.BaseWrapper | None = None

    # connect — запускаем приложение или цепляемся к уже открытому.
    # Метод ищет главное окно по регулярному выражению title_re. Если окно нашлось — просто «подключаемся» к нему. Если нет — стартуем приложение (cmd_line) и ждём появления окна.
    # UWP-приложения требуют особого запуска через explorer.exe или через powershell Start-Process (Application.start() для UWP не работает). Метод connect() будет обрабатывать случаи, когда приложение запускается через библиотеку pywinauto -  Application.start() и случаи, когда приложение запускается через explorer.exe
    # Application.start() в pywinauto запускает процесс по переданной командной строке или по пути до .exe файла и привязывает объект Application к только что созданному процессу, сохраняя его PID и дескриптор. Дополнительный Application().connect() не нужен. Объект уже подключен к процессу, поэтому можно сразу искать окна, элементы и вызывать методы.
    def connect(self, cmd_line: str, *, title_re: str, timeout: int = 15) -> None:
        # 1. Пытаемся присоединиться к уже запущенному экземпляру

        dlg = self._find_main_window(title_re, raise_error=False)
        if dlg:
            self.app = Application(backend=self.backend).connect(handle=dlg.handle)
            self.main = self.app.window(handle=dlg.handle)
            return

        # 2. Запускаем приложение (особая обработка UWP / MS Store через explorer.exe)
        if cmd_line.lower().startswith("shell:appsfolder"):
            # Для UWP приложений необходим запуск через explorer.exe или через powershell Start-Process
            subprocess.Popen(
                ["explorer.exe", cmd_line],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.app = None  # подключимся, когда окно появится
        else:
            self.app = Application(backend=self.backend).start(cmd_line)

        # 3. Ожидаем появления главного окна
        dlg = self._find_main_window(title_re, timeout=timeout, raise_error=False)
        if not dlg:
            raise TimeoutError(
                f"Окно, соответствующее {title_re!r}, не найдено за {timeout} с после запуска"
            )

        # 4. Подключаемся, если запускали через explorer.exe (self.app ещё не инициализирован)
        if self.app is None:
            self.app = Application(backend=self.backend).connect(handle=dlg.handle)
            # Сохраняем WindowSpecification, а не UIAWrapper, так как у UIAWrapper не возможно будет получить дамп дерева контролов.
            self.main = self.app.window(handle=dlg.handle)

    # wait_for — ждём, пока элемент появится/станет готов.
    # Принимает локатор (список составленных локаторов будет показан далее), нужное состояние и тайм-аут. Возвращает найденный контрол или кидает ошибку, если время вышло.
    # Окно может быть в одном из следующих состояний. Также допускается комбинирование состояний через пробел.
    # exists (существует) — означает, что окно имеет валидный дескриптор;
    # visible (видимое) — означает, что окно не скрыто;
    # enabled (активное) — означает, что окно не заблокировано;
    # ready (готово) — означает, что окно видимое и активное (visible + enabled);
    # active (на переднем плане) — означает, что окно является активным (имеет фокус).
    def wait_for(
        self,
        locator: Mapping[str, Any],
        *,
        state: str = "exists",
        timeout: int = 5,
    ):
        if not self.main:
            raise RuntimeError("Приложение не проинициализировано.")
        return self.main.child_window(**locator).wait(state, timeout=timeout)

    # click — кликаем по элементу, а при неудаче — по картинке. Используем комбинированный подход.
    # Сначала пытаемся найти контрол через wait_for и нажать на него. Если не удалось найти элемент по локатору, используем pyautogui для сравнения скриншота элемента fallback_img с экраном. Затем кликаем по координатам найденного элемента.
    # Поиск элемента по картинке может быть полезен, если приложение использует защиту в виде динамически меняющихся локаторов. Например, когда меняются AutomationId, Title или Control Type. Также это актуально для кастомных элементов управления с пустыми свойствами UIA и контролов, созданных с помощью DirectX или OpenGL.
    def click(
        self,
        locator: Mapping[str, Any],
        *,
        timeout: int = 5,
        fallback_img: Path | None = None,
    ) -> None:
        try:
            ctrl = self.wait_for(locator, timeout=timeout)
            logger.info(f"Контрол найден по локатору {locator}")

            ctrl.click_input()

        except (TimeoutError, RuntimeError):
            logger.warning(f"Локатор {locator} (timeout={timeout}) не найден.")

        logger.info(f"Локатор {locator} ищем по картинке {fallback_img}")

        pt = pyautogui.locateCenterOnScreen(str(fallback_img), confidence=0.9)

        if not pt:
            raise LookupError(
                f"Элемент не найден ни по локатору {locator} ни по картинке {fallback_img}."
            )

    # type_keys — вводим текст, при желании жмём Enter.
    # Активное окно уже известно, поэтому напрямую посылаем последовательность клавиш. Аргумент enter=True добавляет {ENTER} в конец строки — удобно для поиска или отправки сообщений.
    def type_keys(self, text: str, *, enter: bool = False) -> None:
        if not self.main:
            raise RuntimeError("Приложение не проинициализировано.")

        self.main.type_keys(
            text + ("{ENTER}" if enter else ""), with_spaces=True, set_foreground=False
        )

    # get_focus_on_window — вытаскиваем окно на передний план.
    # Нужно, когда приложение оказалось «под другими». Ищем окно по title_re (или берём main) и вызываем set_focus().
    def get_focus_on_window(self, title_re: str | None = None, timeout: int = 5) -> None:
        target = None

        if title_re:
            try:
                target = (
                    Desktop(backend=self.backend)
                    .window(title_re=title_re)
                    .wait("exists", timeout=timeout)
                )

            except TimeoutError as e:
                raise TimeoutError(f"Окно '{title_re}' не найдено за {timeout}с") from e

        else:
            target = self.main

        if not target:
            raise RuntimeError("Нет доступного окна для фокусировки.")

        target.set_focus()

    # _find_main_window — поиск главного окна.
    # Внутренний метод перебирает несколько возможных ControlType (Window, Pane, None), пока не найдёт видимое и готовое окно, заголовок которого совпадает с регулярным выражением title_re. Если ничего не найдено и raise_error=True, выбрасывает TimeoutError.
    def _find_main_window(
        self,
        title_re: str,
        timeout: int = 5,
        raise_error: bool = True,
    ):
        """Ищем главное окно, пробуя несколько ControlType."""

        for ctype in self._FALLBACK_CTYPES:
            try:
                w = (
                    Desktop(backend=self.backend)
                    .window(
                        title_re=title_re,
                        control_type=ctype,
                    )
                    .wait("visible ready", timeout=timeout)
                )

                return w

            except pywinauto.timings.TimeoutError:
                continue

        if raise_error:
            raise TimeoutError(f"Window '{title_re}' not found")

        return None

    # wait_for_keyboard_focus –ожидание фокуса элемента.
    # Метод позволяет дождаться клавиатурного фокуса элемента. В цикле опрашиваем has_keyboard_focus() (для UIA-обёртки это свойство HasKeyboardFocus) и, если по истечении тайм-аута фокуса нет, бросаем TimeoutError. При успехе метод возвращает сам контрол, позволяя сразу выполнять следующее действие. Такой приём устраняет «флаки» в сценариях, где UI не успевает обработать предыдущую команду.
    def wait_for_keyboard_focus(
        self,
        locator: Mapping[str, Any],
        *,
        timeout: int = 5,
        poll: float = 0.05,
    ):
        """Ждём, пока элемент получит клавиатурный фокус (HasKeyboardFocus=True)."""

        ctrl = self.wait_for(locator, state="exists", timeout=timeout)

        start = monotonic()

        while monotonic() - start < timeout:
            if ctrl.has_keyboard_focus():
                return ctrl  # успех

            sleep(poll)

        raise TimeoutError(f"Элемент {locator} не получил фокус за {timeout} с")

    # close — закрываем приложение.
    # Если главное окно (main) известно, вызываем у него close(). Полезно в конце теста, чтобы не оставлять «висящие» процессы.
    def close(self) -> None:
        if self.main:
            self.main.close()

    # Полезный лайфхак — это делать скриншот всего экрана (например с помощью pyautogui.screenshot()), если не удалось найти элемент по имеющимся картинкам, и из этого скриншота в ручную вырезать нужную область с элементом.
    def load_images(folder):
        """
        Загружает все изображения PNG из папки внутри ./ui_elements.
        :param str folder: Относительный путь внутри ./ui_elements, например "Whatsapp/start_button"
        :returns: Список кортежей (PIL.Image.Image, str), где str — полный путь к изображению
        """
        base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_elements", folder)
        images = []

        if not os.path.isdir(base_path):
            raise FileNotFoundError(f"Папка не найдена: {base_path}")

        for file_name in os.listdir(base_path):
            if file_name.lower().endswith(".png"):
                image_path = os.path.join(base_path, file_name)
                with Image.open(image_path) as img:
                    images.append((img.copy(), image_path))

        return images

    def locate_on_screen(self, folder, confidence=0.8, min_search_time=10):
        """

        Пытается найти одно из указанных изображений в папке на экране, пока оно не будет найдено.

        :param str folder: Путь к папке содержит элементы изображений с расширением ".png".

        :param float trust: Уровень уверенности — это число с плавающей точкой от 0 до 1

        для pyautogui.locateOnScreen.

        :param int min_search_time: Количество времени в секундах для повторения поиска.

        :returns: Объект Box(NamedTuple) с координатами элемента на экране или None.

        """

        images = self.load_images(folder)

        for image, filename in images:
            try:
                location = pyautogui.locateOnScreen(
                    image, confidence=confidence, minSearchTime=min_search_time
                )

                if location is not None:
                    # После поиска элемента мы получаем координаты его верхнего левого угла, ширину и высоту. Чтобы нажать на нужную часть кнопки, центрируемся по её середине.

                    return pyautogui.center(
                        (location.left, location.top, location.width, location.height)
                    )

            except pyautogui.ImageNotFoundException:
                logger.inf(f"Изображение не найдено, имя файла: {filename}")

        return None
