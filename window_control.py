import win32gui
def move_resize(x: int, y: int, width: int, height: int, title: str="Google Chrome"):
    # titleを含むウィンドウハンドルを取得
    def enum_window_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(enum_window_callback, results)
    if not results:
        print(f"No window found")
        return
    for hwnd in results:
        print(f"move and resize window: {win32gui.GetWindowText(hwnd)}")
        win32gui.MoveWindow(hwnd, x, y, width, height, True)

move_resize(100, 100, 800, 600)




# ウィンドウタイトルの一部を指定してウィンドウハンドルを取得
def find_window_by_title(title_part):
    def enum_window_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and title_part in win32gui.GetWindowText(hwnd):
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(enum_window_callback, results)
    return results

# ウィンドウの位置とサイズを変更
def move_and_resize_window(hwnd, x, y, width, height):
    win32gui.MoveWindow(hwnd, x, y, width, height, True)

# # 操作するブラウザウィンドウのタイトルを一部指定
# target_title = "Google Chrome"
# hwnds = find_window_by_title(target_title)

# if hwnds:
#     for hwnd in hwnds:
#         print(f"Found window: {win32gui.GetWindowText(hwnd)}")
#         move_and_resize_window(hwnd, 100, 100, 800, 600)  # x, y, width, height
# else:
#     print("No matching windows found.")
