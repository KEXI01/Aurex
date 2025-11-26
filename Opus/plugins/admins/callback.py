import asyncio

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import YouTube, app
from Opus.core.call import Signal
from Opus.misc import SUDOERS, db
from Opus.utils.database import (
    get_active_chats,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_music_playing,
    is_nonadmin_chat,
    music_off,
    music_on,
    set_loop,
    get_thumb_setting,
)
from Opus.utils.decorators.language import languageCB
from Opus.utils.formatters import seconds_to_min
from Opus.utils.inline import close_markup, stream_markup, stream_markup_timer
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.thumbnails import get_thumb
from config import (
    BANNED_USERS,
    SUPPORT_CHAT,
    SOUNCLOUD_IMG_URL,
    STREAM_IMG_URL,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
    adminlist,
    confirmer,
    votemode,
)
from strings import get_string

checker = {}
upvoters = {}

async def delete_after_delay(message, delay=10):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

def parse_duration_to_seconds(dur):
    try:
        if isinstance(dur, int):
            return dur
        parts = str(dur).split(":")
        parts = [int(p) for p in parts if p != ""]
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except:
        return 0
    return 0

@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention
    thumb_mode = await get_thumb_setting(chat_id)

    if command == "UpVote":
        if chat_id not in votemode:
            votemode[chat_id] = {}
        if chat_id not in upvoters:
            upvoters[chat_id] = {}

        voters = (upvoters[chat_id]).get(CallbackQuery.message.id)
        if not voters:
            upvoters[chat_id][CallbackQuery.message.id] = []

        vote = (votemode[chat_id]).get(CallbackQuery.message.id)
        if not vote:
            votemode[chat_id][CallbackQuery.message.id] = 0

        if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
            (upvoters[chat_id][CallbackQuery.message.id]).remove(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] -= 1
        else:
            (upvoters[chat_id][CallbackQuery.message.id]).append(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] += 1
        upvote = await get_upvote_count(chat_id)
        get_upvotes = int(votemode[chat_id][CallbackQuery.message.id])
        if get_upvotes >= upvote:
            votemode[chat_id][CallbackQuery.message.id] = upvote
            try:
                exists = confirmer[chat_id][CallbackQuery.message.id]
                current = db[chat_id][0]
            except:
                return await CallbackQuery.edit_message_text(f"ғᴀɪʟᴇᴅ.")
            try:
                if current["vidid"] != exists["vidid"]:
                    return await CallbackQuery.edit_message_text(_["admin_35"])
                if current["file"] != exists["file"]:
                    return await CallbackQuery.edit_message_text(_["admin_35"])
            except:
                return await CallbackQuery.edit_message_text(_["admin_36"])
            try:
                await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
            except:
                pass
            command = counter
            mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if (
                CallbackQuery.from_user.id
                in upvoters[chat_id][CallbackQuery.message.id]
            ):
                await CallbackQuery.answer(_["admin_38"], show_alert=True)
            else:
                await CallbackQuery.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"UpVote {get_upvotes}",
                            callback_data=f"ADMIN  UpVote|{chat_id}_{counter}",
                        )
                    ]
                ]
            )
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            return await CallbackQuery.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            if CallbackQuery.from_user.id not in SUDOERS:
                admins = adminlist.get(CallbackQuery.message.chat.id)
                if not admins:
                    return await CallbackQuery.answer(_["admin_13"], show_alert=True)
                else:
                    if CallbackQuery.from_user.id not in admins:
                        return await CallbackQuery.answer(
                            _["admin_14"], show_alert=True
                        )
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Signal.pause_stream(chat_id)
        sent_msg = await CallbackQuery.message.reply_text(
            _["admin_2"].format(mention), reply_markup=close_markup(_)
        )
        asyncio.create_task(delete_after_delay(sent_msg, 10))
    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Signal.resume_stream(chat_id)
        sent_msg = await CallbackQuery.message.reply_text(
            _["admin_4"].format(mention), reply_markup=close_markup(_)
        )
        asyncio.create_task(delete_after_delay(sent_msg, 10))
    elif command == "Stop" or command == "End":
        await CallbackQuery.answer()
        try:
            await Signal.stop_stream(chat_id)
        except:
            pass
        try:
            await music_off(chat_id)
        except:
            pass
        try:
            await set_loop(chat_id, 0)
        except:
            pass
        try:
            if db.get(chat_id) and db[chat_id][0].get("mystic"):
                await db[chat_id][0]["mystic"].delete()
        except:
            pass
        try:
            db.pop(chat_id, None)
        except:
            pass
        sent_msg = await CallbackQuery.message.reply_text(
            _["admin_5"].format(mention), reply_markup=close_markup(_)
        )
        asyncio.create_task(delete_after_delay(sent_msg, 10))
        await CallbackQuery.message.delete()
    elif command == "Skip" or command == "Replay":
        check = db.get(chat_id)
        if not check:
            return await CallbackQuery.answer(_["admin_27"], show_alert=True)

        if command == "Skip":
            txt = f"> ᴛʀᴀᴄᴋ sᴋɪᴩᴩᴇᴅ\n•ʙʏ : {mention} 🛸"
            popped = None
            try:
                popped = check.pop(0)
                if popped:
                    await auto_clean(popped)
                if not check:
                    try:
                        await CallbackQuery.edit_message_text(txt)
                    except:
                        pass
                    sent_msg = await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    asyncio.create_task(delete_after_delay(sent_msg, 10))
                    try:
                        if db.get(chat_id) and db[chat_id][0].get("mystic"):
                            await db[chat_id][0]["mystic"].delete()
                    except:
                        pass
                    try:
                        await Signal.stop_stream(chat_id)
                    except:
                        pass
                    try:
                        await music_off(chat_id)
                    except:
                        pass
                    try:
                        await set_loop(chat_id, 0)
                    except:
                        pass
                    try:
                        db.pop(chat_id, None)
                    except:
                        pass
                    return
            except:
                pass
        else:
            txt = f"≥ ᴛʀᴀᴄᴋ ʀᴇ-ᴘʟᴀʏᴇᴅ\n•ʙʏ : {mention} Flying Saucer"

        try:
            if db.get(chat_id) and db[chat_id][0].get("mystic"):
                await db[chat_id][0]["mystic"].delete()
        except:
            pass

        await CallbackQuery.answer()
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        duration = check[0]["dur"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        status = True if str(streamtype) == "video" else None
        db[chat_id][0]["played"] = 0
        exis = check[0].get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0


        button = stream_markup(_, chat_id)

        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await CallbackQuery.message.reply_text(
                    text=_["admin_7"].format(title),
                    reply_markup=close_markup(_),
                )
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Signal.skip_stream(chat_id, link, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            caption_text = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                duration,
                user,
            )
            if thumb_mode:
                img = await get_thumb(videoid)
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

        elif "vid_" in queued:
            mystic_dl = await CallbackQuery.message.reply_text(
                _["call_7"], disable_web_page_preview=True
            )
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic_dl,
                    videoid=True,
                    video=status,
                )
            except:
                return await mystic_dl.edit_text(_["call_6"])
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Signal.skip_stream(chat_id, file_path, video=status, image=image)
            except:
                return await mystic_dl.edit_text(_["call_6"])
            caption_text = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                duration,
                user,
            )
            if thumb_mode:
                img = await get_thumb(videoid)
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            await mystic_dl.delete()
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

        elif "index_" in queued:
            try:
                await Signal.skip_stream(chat_id, videoid, video=status)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            caption_text = _["stream_2"].format(user)
            if thumb_mode:
                run = await CallbackQuery.message.reply_photo(
                    photo=STREAM_IMG_URL,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

        else:
            if videoid == "telegram":
                image = None
            elif videoid == "soundcloud":
                image = None
            else:
                try:
                    image = await YouTube.thumbnail(videoid, True)
                except:
                    image = None
            try:
                await Signal.skip_stream(chat_id, queued, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            if videoid in ["telegram", "soundcloud"]:
                caption_text = _["stream_1"].format(
                    SUPPORT_CHAT, title[:23], duration, user
                )
                photo_url = TELEGRAM_AUDIO_URL if streamtype == "audio" else TELEGRAM_VIDEO_URL
                if videoid == "soundcloud":
                    photo_url = SOUNCLOUD_IMG_URL if streamtype == "audio" else TELEGRAM_VIDEO_URL
                if thumb_mode:
                    run = await CallbackQuery.message.reply_photo(
                        photo=photo_url,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                caption_text = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    duration,
                    user,
                )
                if thumb_mode:
                    img = await get_thumb(videoid)
                    run = await CallbackQuery.message.reply_photo(
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

async def markup_timer():
    while not await asyncio.sleep(7):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing or not playing:
                    continue
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                mystic = playing[0].get("mystic")
                if not mystic:
                    continue
                try:
                    check = checker[chat_id][mystic.id]
                    if check is False:
                        continue
                except:
                    pass
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except:
                    _ = get_string("en")
                try:
                    buttons = stream_markup_timer(
                        _,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                    )
                    await mystic.edit_reply_markup(
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except:
                    continue
            except:
                continue

asyncio.create_task(markup_timer())
