import os
import time
import json
import requests
from requests.exceptions import SSLError, ConnectionError, ReadTimeout
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TransferSpeedColumn

console = Console()

WATCH_FOLDER = "downloads"
BOT_TOKEN = ""

# destinations (group/channel)
CHAT_ID_MAIN = ""       # can be empty
CHAT_ID_SUPPORT = ""    # can be empty
TEMP_FILE = "temp.json"


class ProgressFile:
    def __init__(self, filename, progress, task_id):
        self._file = open(filename, 'rb')
        self.filename = filename
        self.filesize = os.path.getsize(filename)
        self.progress = progress
        self.task_id = task_id
        self._read_bytes = 0

    def read(self, chunk_size=-1):
        data = self._file.read(chunk_size)
        if not data:
            return data
        self._read_bytes += len(data)
        self.progress.update(self.task_id, completed=self._read_bytes)
        return data

    def __getattr__(self, attr):
        return getattr(self._file, attr)

    def __del__(self):
        if not self._file.closed:
            self._file.close()


def send_file(bot_token, chat_id, filename, caption="", max_retries=3):
    """Uploads file to Telegram with progress + caption, includes retries"""
    if not chat_id:
        console.print(f"[yellow]Skipping upload — no chat_id provided.[/yellow]")
        return False

    url = f'https://api.telegram.org/bot{bot_token}/sendDocument'
    file_size = os.path.getsize(filename)
    console.print(f"[green]File size: {file_size / (1024 * 1024):.2f} MB[/green]")

    progress = Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        TransferSpeedColumn(),
        "•",
        TextColumn("{task.completed}/{task.total} bytes"),
        console=console,
    )

    for attempt in range(1, max_retries + 1):
        try:
            with progress:
                task_id = progress.add_task(f"[cyan]Uploading to {chat_id}... (Attempt {attempt})", total=file_size)
                progress_file = ProgressFile(filename, progress, task_id)

                multipart_data = {
                    'document': (os.path.basename(filename), progress_file),
                    'chat_id': (None, chat_id),
                    'caption': (None, caption),
                }

                response = requests.post(url, files=multipart_data, timeout=180)

            if response.ok:
                console.print(f"[bold green]File '{os.path.basename(filename)}' sent successfully to {chat_id}![/bold green]")
                return True
            else:
                console.print(f"[bold red]Failed to send file to {chat_id}: {response.text}[/bold red]")

        except (SSLError, ConnectionError, ReadTimeout) as e:
            console.print(f"[red]Network/SSL error while sending to {chat_id}: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Unexpected error sending to {chat_id}: {e}[/red]")

        if attempt < max_retries:
            wait = 2 ** attempt
            console.print(f"[yellow]Retrying in {wait}s...[/yellow]")
            time.sleep(wait)
        else:
            console.print(f"[bold red]Failed after {max_retries} attempts for {chat_id}[/bold red]")

    return False


def get_caption(filename):
    """Use .txt with same basename as caption, fallback to filename (Unicode safe)"""
    base, _ = os.path.splitext(filename)
    caption_file = base + ".txt"
    if os.path.exists(caption_file):
        try:
            with open(caption_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            return os.path.basename(filename)
    return os.path.basename(filename)


def is_file_stable(filepath, wait_time=5):
    """Check if file size is stable for wait_time seconds"""
    try:
        initial_size = os.path.getsize(filepath)
        time.sleep(wait_time)
        return os.path.getsize(filepath) == initial_size
    except FileNotFoundError:
        return False


def load_sent_files():
    """Load list of sent files from temp.json"""
    if os.path.exists(TEMP_FILE):
        try:
            with open(TEMP_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def save_sent_files(sent_files):
    """Save list of sent files to temp.json"""
    try:
        with open(TEMP_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_files), f, ensure_ascii=False, indent=2)
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to save temp.json: {e}[/yellow]")


def watch_folder():
    console.print(f"[cyan]Watching folder: {WATCH_FOLDER}[/cyan]")
    sent_files = load_sent_files()

    while True:
        try:
            files = [os.path.join(WATCH_FOLDER, f) for f in os.listdir(WATCH_FOLDER)]
            for f in files:
                if os.path.isfile(f) and not f.endswith(".txt") and f not in sent_files:
                    if not is_file_stable(f, wait_time=5):
                        continue

                    caption = get_caption(f)

                    success_main = send_file(BOT_TOKEN, CHAT_ID_MAIN, f, caption)
                    success_support = send_file(BOT_TOKEN, CHAT_ID_SUPPORT, f, caption)

                    if success_main or success_support:
                        sent_files.add(f)
                        save_sent_files(sent_files)

            time.sleep(4)
        except KeyboardInterrupt:
            console.print("[red]Stopped watching.[/red]")
            break


if __name__ == "__main__":
    watch_folder()
