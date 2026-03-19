import os
import re
import shlex
import subprocess
import sys
import traceback
from io import StringIO
from tempfile import NamedTemporaryFile
from time import time

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import LOGGER_ID, OWNER_ID
from Opus import app

PROTECTED_PATTERNS = [
    "__main__.py",
    ".session",
    ".session-journal",
    "config.py",
    ".env",
    "venv",
    ".venv",
    "database.py",
    "__pycache__",
    "strings/session",
    "cookies.txt",
    "cookie_refresh_time.txt",
]
BLOCKED_EXECUTABLES = {
    "mv",
    "cp",
    "chmod",
    "chown",
    "sudo",
    "su",
    "bash",
    "zsh",
    "fish",
    "python",
    "git",
    "find",
    "locate",
    "wget",
    "curl",
    "scp",
    "rsync",
    "pkill",
    "kill",
    "killall",
    "reboot",
    "shutdown",
    "service",
    "systemctl",
}
PROTECTED_MSG = (
    "<b>⚠️ Protected resource detected.</b>\n"
    "<i>This eval/shell command was blocked to protect important files.</i>"
)
BLOCKED_CMD_MSG = (
    "<b>⚠️ Blocked command.</b>\n"
    "<i>This shell command is not allowed in protected mode.</i>"
)


def is_protected_command(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(pattern.lower() in lower for pattern in PROTECTED_PATTERNS)


def is_blocked_shell_command(text: str) -> bool:
    if not text:
        return False
    try:
        parts = shlex.split(text)
    except Exception:
        return True
    if not parts:
        return False
    return parts[0].lower() in BLOCKED_EXECUTABLES


async def aexec(code, client, message):
    safe_builtins = {
        "print": print,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "int": int,
        "str": str,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "sorted": sorted,
        "__build_class__": __build_class__,
        "Exception": Exception,
    }

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        blocked = {
            "os",
            "sys",
            "subprocess",
            "pathlib",
            "config",
            "dotenv",
            "inspect",
            "shutil",
            "glob",
            "socket",
            "requests",
            "httpx",
            "urllib",
            "importlib",
            "pickle",
            "marshal",
        }
        if name in blocked:
            raise ImportError("Access to this module is blocked in eval.")
        return __import__(name, globals, locals, fromlist, level)

    safe_builtins["__import__"] = safe_import
    safe_globals = {"__builtins__": safe_builtins}

    exec(
        "async def __aexec(client, message): " + "".join(f"\n {a}" for a in code.split("\n")),
        safe_globals,
    )
    return await safe_globals["__aexec"](client, message)


async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user and msg.from_user.is_self else msg.reply
    await func(**kwargs)


def private_and_owner(filter, client: Client, message: Message):
    return bool(
        message.from_user
        and message.from_user.id == OWNER_ID
        and message.chat.id == LOGGER_ID
    )


def build_safe_env():
    return {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


@app.on_message(
    filters.command("eval")
    & filters.user(OWNER_ID)
    & filters.create(private_and_owner)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def executor(client: Client, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(
            message,
            text="<b>What do you want to execute?</b>",
        )

    try:
        cmd = message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await message.delete()

    if is_protected_command(cmd):
        return await edit_or_reply(message, text=PROTECTED_MSG)

    normalized = cmd.strip()
    if normalized in ("exit", "exit()", "exit ()", "quit", "quit()", "quit ()"):
        await edit_or_reply(
            message,
            text="<b>Shutting down...</b>",
        )
        os._exit(0)

    t1 = time()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None

    try:
        await aexec(cmd, client, message)
    except Exception:
        exc = traceback.format_exc()

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    evaluation = "\n"
    if exc:
        evaluation += exc
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"

    final_output = f"<b>⥤ Result:</b>\n<pre language='python'>{evaluation}</pre>"

    t2 = time()
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⏳",
                    callback_data=f"runtime {round(t2 - t1, 3)} Seconds",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"forceclose abc|{message.from_user.id}",
                ),
            ]
        ]
    )

    if len(final_output) > 4096:
        with NamedTemporaryFile("w+", encoding="utf-8", delete=False, suffix=".txt") as out_file:
            out_file.write(str(evaluation))
            filename = out_file.name

        await message.reply_document(
            document=filename,
            caption=(
                f"<b>⥤ Eval:</b>\n<code>{cmd[0:980]}</code>\n\n"
                f"<b>⥤ Result:</b>\nAttached document"
            ),
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        try:
            os.remove(filename)
        except Exception:
            pass
    else:
        await edit_or_reply(
            message,
            text=final_output,
            reply_markup=keyboard,
        )


@app.on_message(
    filters.command("sh")
    & filters.user(OWNER_ID)
    & filters.create(private_and_owner)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(
            message,
            text="<b>Example:</b>\n/sh ls",
        )

    text = message.text.split(None, 1)[1].strip()
    if not text:
        return await edit_or_reply(
            message,
            text="<b>Example:</b>\n/sh ls",
        )

    if is_protected_command(text):
        return await edit_or_reply(message, text=PROTECTED_MSG)

    safe_env = build_safe_env()

    if "\n" in text:
        code = text.split("\n")
        output = ""
        for x in code:
            x = x.strip()
            if not x:
                continue

            if is_protected_command(x):
                output += f"<b>{x}</b>\n[blocked: protected resource]\n\n"
                continue

            if is_blocked_shell_command(x):
                output += f"<b>{x}</b>\n[blocked: restricted command]\n\n"
                continue

            try:
                shell = shlex.split(x)
                process = subprocess.Popen(
                    shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=safe_env,
                    cwd=os.getcwd(),
                )
                stdout, stderr = process.communicate(timeout=20)
                output += f"<b>{x}</b>\n{stdout.decode(errors='replace')}\n{stderr.decode(errors='replace')}\n"
            except subprocess.TimeoutExpired:
                process.kill()
                output += f"<b>{x}</b>\n[blocked: command timeout]\n\n"
            except Exception as err:
                return await edit_or_reply(
                    message,
                    text=f"<b>ERROR:</b>\n<pre>{err}</pre>",
                )
    else:
        if is_blocked_shell_command(text):
            return await edit_or_reply(message, text=BLOCKED_CMD_MSG)

        try:
            shell = shlex.split(text)
            process = subprocess.Popen(
                shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=safe_env,
                cwd=os.getcwd(),
            )
            stdout, stderr = process.communicate(timeout=20)
            output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        except subprocess.TimeoutExpired:
            process.kill()
            return await edit_or_reply(
                message,
                text="<b>ERROR:</b>\n<pre>Command timed out.</pre>",
            )
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errors_text = traceback.format_exception(
                etype=exc_type,
                value=exc_obj,
                tb=exc_tb,
            )
            return await edit_or_reply(
                message,
                text=f"<b>ERROR:</b>\n<pre>{''.join(errors_text)}</pre>",
            )

    if not output.strip():
        output = "None"

    if len(output) > 4090:
        with NamedTemporaryFile("w+", encoding="utf-8", delete=False, suffix=".txt") as file:
            file.write(output)
            temp_name = file.name
        await app.send_document(
            message.chat.id,
            temp_name,
            reply_to_message_id=message.id,
            caption="<code>Output</code>",
        )
        try:
            os.remove(temp_name)
        except Exception:
            pass
    else:
        await edit_or_reply(
            message,
            text=f"<b>OUTPUT:</b>\n<pre>{output}</pre>",
        )

    await message.stop_propagation()


@app.on_callback_query(filters.regex(r"runtime"))
async def runtime_func_cq(_, cq):
    runtime = cq.data.split(None, 1)[1]
    await cq.answer(runtime, show_alert=True)


@app.on_callback_query(filters.regex("forceclose"))
async def forceclose_command(_, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    query, user_id = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                "This action is not for you.",
                show_alert=True,
            )
        except Exception:
            return
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except Exception:
        return
