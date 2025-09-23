import sys
import traceback
import os
from functools import wraps
from datetime import datetime

import aiofiles
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden

from Opus import app
from Opus.utils.exceptions import is_ignored_error
from Opus.utils.pastebin import OpusBin

INTERNAL_ERROR_LOG_FILE = "internal_errors.log"  # Single file for all internal errors

# ========== Safe Logging ==========

async def safe_send_message(text: str, filename: str = None):
    """
    Save error messages to a file or print to console.
    """
    try:
        if not filename:
            filename = f"error_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        path = f"{filename}.txt"
        async with aiofiles.open(path, "w") as f:
            await f.write(text)
        print(f"Error logged to file: {path}")
    except Exception as e:
        # Last resort: Print to console
        print(f"CRITICAL: Failed to log error - {str(e)}")
        print(f"Original error text: {text}")

# ========== Paste Fallback ==========

async def send_large_error(text: str, caption: str, filename: str):
    """
    Handle large error messages by uploading to paste service or saving to file.
    """
    try:
        paste_url = await OpusVBin(text)
        if paste_url:
            await safe_send_message(f"{caption}\n\n🔗 Paste: {paste_url}")
            return
    except Exception:
        pass

    # Fallback to file
    try:
        path = f"{filename}.txt"
        async with aiofiles.open(path, "w") as f:
            await f.write(text)
        await safe_send_message(f"Error log saved to: {path}")
        os.remove(path)
    except Exception as e:
        await safe_send_message(f"Failed to create error log file: {str(e)}\n\nOriginal error:\n{text}")

# ========== Formatting & Routing ==========

def format_traceback(err, tb, label: str, extras: dict = None) -> str:
    """
    Format error traceback for logging.
    """
    exc_type = type(err).__name__
    parts = [
        f"🚨 <b>{label} Captured</b>",
        f"📍 <b>Error Type:</b> <code>{exc_type}</code>"
    ]
    if extras:
        parts.extend([f"📌 <b>{k}:</b> <code>{v}</code>" for k, v in extras.items()])
    parts.append(f"\n<b>Traceback:</b>\n<pre>{tb}</pre>")
    return "\n".join(parts)

async def handle_trace(err, tb, label, filename, extras=None):
    """
    Handle error tracing with safe logging.
    """
    if is_ignored_error(err):
        return  # Skip ignored errors

    try:
        caption = format_traceback(err, tb, label, extras)
        if len(caption) > 4096:
            await send_large_error(tb, caption.split("\n\n")[0], filename)
        else:
            await safe_send_message(caption, filename)
    except Exception as log_err:
        # Prevent infinite recursion in error logging
        fallback_msg = f"CRITICAL: Error in error handler - {str(log_err)}\nOriginal error: {str(err)}"
        try:
            async with aiofiles.open(f"critical_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w") as f:
                await f.write(f"{fallback_msg}\n\nOriginal traceback:\n{tb}")
        except Exception:
            print(fallback_msg)

async def log_internal_error(err, tb, extras=None):
    """
    Log internal errors to a single consolidated file.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"\n{'='*60}",
            f"Internal Error @ {timestamp}",
            f"Error Type: {type(err).__name__}",
            f"Error Message: {str(err)}",
            *(f"{key}: {val}" for key, val in (extras or {}).items()),
            f"{'='*60}",
            "Traceback:",
            tb.strip(),
            f"{'='*60}\n"
        ]
        async with aiofiles.open(INTERNAL_ERROR_LOG_FILE, "a") as log:
            await log.write("\n".join(lines))
    except Exception as e:
        print(f"Failed to log internal error to file: {str(e)}")
        # Fallback to console
        print(f"Internal Error ({timestamp}): {str(err)}")
        print(f"Traceback:\n{tb}")

# ========== Decorators ==========

def capture_err(func):
    """
    Handles errors in command message handlers.
    Logs only unignored errors.
    """
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except ChatWriteForbidden:
            try:
                await app.leave_chat(message.chat.id)
            except Exception:
                pass  # Ignore errors when leaving chat
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "User": message.from_user.mention if message.from_user else "N/A",
                "Command": message.text or message.caption or "N/A",
                "Chat ID": message.chat.id
            }
            filename = f"error_log_{message.chat.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Error", filename, extras)
            # Don't re-raise the error to prevent crash
    return wrapper

def capture_callback_err(func):
    """
    Handles errors in callback query handlers.
    Logs only unignored errors.
    """
    @wraps(func)
    async def wrapper(client, callback_query, *args, **kwargs):
        try:
            return await func(client, callback_query, *args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "User": callback_query.from_user.mention if callback_query.from_user else "N/A",
                "Chat ID": callback_query.message.chat.id if callback_query.message else "N/A"
            }
            filename = f"cb_error_log_{callback_query.message.chat.id if callback_query.message else 'unknown'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await handle_trace(err, tb, "Callback Error", filename, extras)
            # Don't re-raise the error to prevent crash
    return wrapper

def capture_internal_err(func):
    """
    Handles errors in background/internal async bot functions.
    Logs all internal errors to a single file.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            extras = {
                "Function": func.__name__,
                "Module": func.__module__ if hasattr(func, '__module__') else "Unknown"
            }
            
            # Log to single internal errors file
            await log_internal_error(err, tb, extras)
            
            # Don't re-raise the error to prevent crash
    return wrapper
