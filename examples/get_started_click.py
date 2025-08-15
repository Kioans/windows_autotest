from pywinauto.application import Application


GET_STARTED_BTN = {
    "title": "Get started",
    "control_type": "Button",
}

app = Application(backend="uia").connect(title="WhatsApp", timeout=10)
main_window = app.window(title="WhatsApp")
main_window.set_focus()
main_window.wait("visible", timeout=10)
start_btn = main_window.child_window(**GET_STARTED_BTN).wait("visible enabled", timeout=10)
start_btn.click_input()
