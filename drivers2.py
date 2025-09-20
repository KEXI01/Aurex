import os
import time
import json
import requests
from rich.console import Console

console = Console()

WATCH_FOLDER = "downloads"
BOT_TOKEN = "YOUR_BOT_TOKEN"

# destinations (group or channel)
CHAT_ID_MAIN = ""
CHAT_ID_SUPPORT = ""

TEMP_FILE = "storm.json"


def send_file(bot_token, chat_id, filename, caption=""):
    url = f'https://api.telegram.org/bot{bot_token}/sendDocument'
    try:
        with open(filename, "rb") as f:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (os.path.basename(filename), f)},
            )
        if response.ok:
            console.print(f"[green]Sent '{os.path.basename(filename)}' to {chat_id}[/green]")
            return True
        else:
            console.print(f"[red]Failed to send to {chat_id}: {response.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]Error sending {filename} to {chat_id}: {e}[/red]")
        return False


def get_caption(filename):
    """Use .txt with same basename as caption, fallback to filename"""
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
        console.print(f"[yellow]Warning: Could not save temp.json: {e}[/yellow]")


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

                    if success_main and success_support:
                        sent_files.add(f)
                        save_sent_files(sent_files)

            time.sleep(2)
        except KeyboardInterrupt:
            console.print("[red]Stopped watching.[/red]")
            break


if __name__ == "__main__":
    watch_folder()
