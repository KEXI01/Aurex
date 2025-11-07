import math
from Opus import app
from config import SUPPORT_CHAT, OWNER_ID
from Opus.utils.formatters import time_to_seconds
from pyrogram.types import InlineKeyboardButton


def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            )
        ],
        [
            InlineKeyboardButton(
                text="ᴏᴡɴᴇʀ 🥀", url=f"tg://openmessage?user_id={OWNER_ID}",
            ),
            InlineKeyboardButton(
                text="sᴜᴩᴩᴏʀᴛ 🥀", url=SUPPORT_CHAT,
            )
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            )
        ],
    ]
    return buttons

def telegram_markup(_, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="ᴍᴇɴᴜ 📄",
                callback_data=f"PanelMarkup None|{chat_id}",
            ),
            InlineKeyboardButton(
                text=_["CLOSEMENU_BUTTON"], callback_data="close"
            ),
        ],
    ]
    return buttons


def stream_markup_timer(_, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur) or 0

    if duration_sec > 0:
        percentage = (played_sec / duration_sec) * 100
    else:
        percentage = 0

    umm = max(0, min(100, math.floor(percentage)))

    if 0 < umm <= 10:
        bar = "[■□□□□□□□□□]"
    elif 10 < umm < 20:
        bar = "[■■□□□□□□□□]"
    elif 20 <= umm < 30:
        bar = "[■■■□□□□□□□]"
    elif 30 <= umm < 40:
        bar = "[■■■■□□□□□□]"
    elif 40 <= umm < 50:
        bar = "[■■■■■□□□□□]"
    elif 50 <= umm < 60:
        bar = "[■■■■■■□□□□]"
    elif 60 <= umm < 70:
        bar = "[■■■■■■■□□□]"
    elif 70 <= umm < 80:
        bar = "[■■■■■■■■□□]"
    elif 80 <= umm < 95:
        bar = "[■■■■■■■■■□]"
    else:
        bar = "[■■■■■■■■■■]"

    username = app.username.replace("@", "")
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{played} {bar} {dur}",
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
        ],
        #[
         #   InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
          #  InlineKeyboardButton(text="ᴇɴᴅ 🍁", callback_data=f"ADMIN Stop|{chat_id}"),
        #],
    ]
    return buttons


def stream_markup(_, chat_id):
    username = app.username.replace("@", "")
    buttons = [
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
        ],
        #[
         #   InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
          #  InlineKeyboardButton(text="ᴇɴᴅ 🍁", callback_data=f"ADMIN Stop|{chat_id}"),
        #],
    ]
    return buttons


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"AyushPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"AyushPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {query}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
    return buttons

def stream_markup2(_, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="▷",
                callback_data=f"ADMIN Resume|{chat_id}",
            ),
            InlineKeyboardButton(
                text="II", callback_data=f"ADMIN Pause|{chat_id}"
            ),
            InlineKeyboardButton(
                text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"
            ),
            InlineKeyboardButton(
                text="▢", callback_data=f"ADMIN Stop|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ᴏᴡɴᴇʀ 🥀", url=f"tg://openmessage?user_id={OWNER_ID}",
            ),
            InlineKeyboardButton(
                text="sᴜᴘᴘᴏʀᴛ 💘",
                url=SUPPORT_CHAT,
            ),
        ],
        [
            InlineKeyboardButton(
                text="sʜᴜғғʟᴇ 🔀",
                callback_data=f"ADMIN Shuffle|{chat_id}",
            ),
            InlineKeyboardButton(
                text="ʟᴏᴏᴩ ➿", callback_data=f"ADMIN Loop|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʙᴀᴄᴋ 🔙",
                callback_data=f"MainMarkup {videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons
