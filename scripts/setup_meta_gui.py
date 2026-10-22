"""Local-only Meta configuration dialog. Never logs or transmits credentials."""
from pathlib import Path
import os
import re
import tempfile
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
CALLBACK = 'http://127.0.0.1:3200/v1/integrations/meta/callback'


def save_configuration(path, app_id, version, secret, callback, rotated):
    """Validate everything before atomically replacing the private .env file."""
    if not rotated:
        raise ValueError('Hãy reset khóa đã gửi vào chat và xác nhận dùng khóa mới.')
    app_id, version, secret = app_id.strip(), version.strip(), secret.strip()
    if not re.fullmatch(r'[0-9]{1,64}', app_id):
        raise ValueError('App ID phải chỉ gồm chữ số.')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+', version):
        raise ValueError('Phiên bản API phải có dạng vNN.0.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', secret):
        raise ValueError('Khóa không đúng định dạng. Dán chỉ giá trị App Secret mới.')
    uri = urlsplit(callback)
    if (uri.username or uri.password or uri.query or uri.fragment
            or uri.path != '/v1/integrations/meta/callback'
            or uri.hostname != '127.0.0.1' or uri.scheme != 'http' or uri.port != 3200):
        raise ValueError('Callback phải là địa chỉ local PAO cổng 3200.')
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Không tìm thấy file cấu hình local an toàn.')
    original = path.read_bytes()
    current = dotenv_values(stream=__import__('io').StringIO(original.decode('utf-8-sig')))
    # Never rotate an existing encryption key, even if it is invalid.
    key = current.get('INTEGRATION_ENCRYPTION_KEY') or Fernet.generate_key().decode()
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        raise ValueError('Khóa mã hóa hiện có không hợp lệ; dừng, không thay khóa.') from None
    updates = {
        'META_ENABLED': 'true', 'META_APP_ID': app_id, 'META_APP_SECRET': secret,
        'META_GRAPH_API_VERSION': version, 'META_REDIRECT_URI': callback,
        'INTEGRATION_ENCRYPTION_KEY': key,
        'META_WRITE_ENABLED': 'false', 'META_AUTOPILOT_ENABLED': 'false',
        'ADS_AUTOPILOT_GLOBAL_ENABLED': 'false',
    }
    lines = original.decode('utf-8-sig').splitlines()
    def replaced(line):
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        return match is not None and match.group(1).upper() in updates
    lines = [line for line in lines if not replaced(line)]
    content = '\n'.join(lines + [f'{k}={v}' for k, v in updates.items()]) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.meta-config-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_bytes() != original:
            raise ValueError('Cấu hình vừa thay đổi bởi tiến trình khác; hãy thử lại.')
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    import tkinter as tk
    from tkinter import messagebox, ttk
    window = tk.Tk()
    window.title('PAO — Cấu hình Meta chỉ đọc')
    window.resizable(False, False)
    panel = ttk.Frame(window, padding=20)
    panel.grid()
    ttk.Label(panel, text='Nhập khóa mới sau khi reset trên Meta. Không gửi khóa vào chat.').grid(
        row=0, column=0, columnspan=2, pady=(0, 14))
    fields = {}
    for row, (name, label, default) in enumerate([
        ('app_id', 'App ID', '798592876170334'),
        ('version', 'Phiên bản API', 'v26.0'),
        ('secret', 'App Secret mới', ''),
        ('callback', 'Callback local', CALLBACK),
    ], start=1):
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)
        entry = ttk.Entry(panel, width=62, show='*' if name == 'secret' else '')
        entry.insert(0, default)
        entry.grid(row=row, column=1, pady=6)
        if name == 'callback':
            entry.configure(state='readonly')
        fields[name] = entry
    menu = tk.Menu(window, tearoff=0)
    menu.add_command(label='Dán / Paste', command=lambda: fields['secret'].event_generate('<<Paste>>'))
    fields['secret'].bind('<Button-3>', lambda event: menu.tk_popup(event.x_root, event.y_root))
    ttk.Label(panel, text='Dán bằng Ctrl+V hoặc chuột phải → Dán. Khóa được che bằng dấu *.\n'
              'Chỉ lưu local; không gọi Meta, không tự restart, không sync hay sửa quảng cáo.').grid(
        row=5, column=0, columnspan=2, sticky='w', pady=12)
    rotated = tk.BooleanVar(value=False)
    ttk.Checkbutton(panel, text='Tôi đã reset khóa bị lộ và đang dùng khóa mới', variable=rotated).grid(
        row=6, column=0, columnspan=2, sticky='w')

    def save():
        try:
            save_configuration(ROOT / '.env', fields['app_id'].get(), fields['version'].get(),
                               fields['secret'].get(), CALLBACK, rotated.get())
        except ValueError as exc:
            messagebox.showerror('Chưa lưu', str(exc), parent=window)
            return
        except Exception:
            # Do not put exceptions, config values or credentials in dialogs/logs.
            messagebox.showerror('Chưa lưu', 'Không lưu được cấu hình. Hãy báo lỗi này, không gửi khóa.', parent=window)
            return
        fields['secret'].delete(0, 'end')
        messagebox.showinfo('Đã lưu local', 'Cấu hình đã lưu. Quyền ghi và Autopilot đều tắt.\n'
                            'Báo “đã cấu hình bằng khóa mới” để kiểm tra và restart PAO.', parent=window)
        window.destroy()

    buttons = ttk.Frame(panel)
    buttons.grid(row=7, column=0, columnspan=2, pady=(16, 0))
    ttk.Button(buttons, text='Lưu cấu hình chỉ đọc', command=save).pack(side='left', padx=8)
    ttk.Button(buttons, text='Hủy', command=window.destroy).pack(side='left', padx=8)
    fields['secret'].focus_set()
    window.mainloop()


if __name__ == '__main__':
    main()
