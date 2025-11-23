import os
import config
import asyncio
from typing import Union

from pyrogram import Client
from strings import get_string
from pytgcalls import PyTgCalls
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardMarkup
from ntgcalls import ConnectionNotFound, TelegramServerError
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    NotInGroupCallError,
)
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    Update,
)
from pytgcalls.types.stream import StreamAudioEnded

from Opus import YouTube, app
from Opus.misc import db
from Opus.logging import LOGGER
from Opus.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
    get_thumb_setting,
)
from Opus.utils.exceptions import AssistantErr
from Opus.utils.formatters import check_duration, seconds_to_min, speed_converter
from Opus.utils.inline.play import stream_markup
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.thumbnails import get_thumb

autoend = {}
counter = {}
db_locks = {}
loop = asyncio.get_event_loop_policy().get_event_loop()

DEFAULT_AQ = AudioQuality.STUDIO
DEFAULT_VQ = VideoQuality.FHD_1080p
ELSE_AQ = AudioQuality.HIGH
ELSE_VQ = VideoQuality.SD_360p

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    return MediaStream(
        audio_path=path,
        media_path=path,
        audio_parameters=DEFAULT_AQ if video else ELSE_AQ,
        video_parameters=DEFAULT_VQ if video else ELSE_VQ,
        video_flags=(MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE),
        ffmpeg_parameters=ffmpeg_params,
    )


async def _clear_(chat_id):
    try:
        if chat_id in db:
            del db[chat_id]
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
    except:
        pass


class Call:
    def __init__(self):
        self.userbot1 = Client(
            "OpusXAss1", config.API_ID, config.API_HASH, session_string=config.STRING1) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "OpusXAss2", config.API_ID, config.API_HASH, session_string=config.STRING2) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "OpusXAss3", config.API_ID, config.API_HASH, session_string=config.STRING3) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "OpusXAss4", config.API_ID, config.API_HASH, session_string=config.STRING4) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "OpusXAss5", config.API_ID, config.API_HASH, session_string=config.STRING5) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()

    
    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute_stream(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute_stream(chat_id)

    async def get_participant(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        return await assistant.get_participants(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            try:
                await assistant.leave_group_call(chat_id)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for client in [self.one, self.two, self.three, self.four, self.five]:
            try:
                await client.leave_group_call(chat_id)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
            except:
                pass
        await _clear_(chat_id)

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                if str(speed) == "0.75":
                    vs = 1.35
                if str(speed) == "1.5":
                    vs = 0.68
                if str(speed) == "2.0":
                    vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path

        dur = await loop.run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)

        stream = dynamic_media_stream(
            out,
            video=(playing[0]["streamtype"] == "video"),
            ffmpeg_params=f"-ss {played} -to {duration}",
        )

        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
        else:
            raise AssistantErr("Umm")

        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_group_call(chat_id)
        except (NoActiveGroupCall, NotInGroupCallError):
            pass
        except:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(link, video=bool(video))
        try:
            await assistant.change_stream(chat_id, stream)
        except:
            try:
                await app.send_message(chat_id, text="Failed to skip stream due to an error.")
            except:
                pass

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(
            file_path,
            video=(mode == "video"),
            ffmpeg_params=f"-ss {to_seek} -to {duration}",
        )
        try:
            await assistant.change_stream(chat_id, stream)
        except:
            pass

    async def stream_call(self, link):
        # Probe VC capability in the log group
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await assistant.join_group_call(config.LOGGER_ID, dynamic_media_stream(link, video=True))
            await asyncio.sleep(0.5)
            try:
                await assistant.leave_group_call(config.LOGGER_ID)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
        except:
            pass

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)

        stream = dynamic_media_stream(link, video=bool(video))

        try:
            await assistant.join_group_call(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except ConnectionNotFound:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            if "phone.CreateGroupCall" in str(e):
                raise AssistantErr(_["call_8"])
            raise AssistantErr("Failed to join voice chat due to an unknown error.")

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=5)

    async def attempt_stream(self, client, chat_id, stream, retries=1):
        for _ in range(retries):
            try:
                await client.change_stream(chat_id, stream)
                return True
            except:
                await asyncio.sleep(0.5)
        return False

    async def check_autoend(self, chat_id):
        if await is_autoend() and chat_id in autoend:
            users = len(await (await group_assistant(self, chat_id)).get_participants(chat_id))
            if users <= 1:
                if chat_id not in autoend:
                    autoend[chat_id] = datetime.now()
                elif datetime.now() - autoend[chat_id] > timedelta(minutes=5):
                    await self.stop_stream(chat_id)
            else:
                autoend.pop(chat_id, None)

    async def change_stream(self, client, chat_id):
        if chat_id not in db_locks:
            db_locks[chat_id] = asyncio.Lock()

        async with db_locks[chat_id]:
            check = db.get(chat_id)
            popped = None
            loop_count = await get_loop(chat_id)

            try:
                if not check or len(check) == 0:
                    await _clear_(chat_id)
                    try:
                        await client.leave_group_call(chat_id)
                    except (NoActiveGroupCall, NotInGroupCallError):
                        pass
                    return

                if loop_count == 0:
                    popped = check.pop(0)
                else:
                    loop_count = loop_count - 1
                    await set_loop(chat_id, loop_count)

                await auto_clean(popped)

                if not check or len(check) == 0:
                    await _clear_(chat_id)
                    try:
                        await client.leave_group_call(chat_id)
                    except (NoActiveGroupCall, NotInGroupCallError):
                        pass
                    return
            except:
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass
                return

            queued = check[0].get("file")
            if not queued:
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass
                return

            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            
            # Check thumbnail setting
            thumb_mode = await get_thumb_setting(original_chat_id)

            db[chat_id][0]["played"] = 0
            if exis := (check[0]).get("old_dur"):
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            is_video = (str(streamtype) == "video")

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    try:
                        await app.send_message(original_chat_id, text=_["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return

                stream = dynamic_media_stream(link, video=is_video)

                if not await self.attempt_stream(client, chat_id, stream):
                    try:
                        await app.send_message(original_chat_id, text=_["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                caption_text = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                )
                
                if thumb_mode:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid, mystic, videoid=True, video=is_video
                    )
                    if not os.path.exists(file_path):
                        await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
                        await _clear_(chat_id)
                        return
                except:
                    await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
                    await _clear_(chat_id)
                    return

                stream = dynamic_media_stream(file_path, video=is_video)

                if not await self.attempt_stream(client, chat_id, stream):
                    try:
                        await app.send_message(original_chat_id, text=_["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                
                caption_text = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                )
                
                if thumb_mode:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                stream = dynamic_media_stream(videoid, video=is_video)
                if not await self.attempt_stream(client, chat_id, stream):
                    try:
                        await app.send_message(original_chat_id, text=_["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return
                button = stream_markup(_, chat_id)
                caption_text = _["stream_2"].format(user)
                
                if thumb_mode:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.STREAM_IMG_URL,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = dynamic_media_stream(queued, video=is_video)

                if not await self.attempt_stream(client, chat_id, stream):
                    try:
                        await app.send_message(original_chat_id, text=_["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    caption_text = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
                    
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=(config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL),
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    caption_text = _["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user)
                    
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.SOUNCLOUD_IMG_URL,
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                         run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    caption_text = _["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        )
                    
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(await self.one.ping)
        if config.STRING2:
            pings.append(await self.two.ping)
        if config.STRING3:
            pings.append(await self.three.ping)
        if config.STRING4:
            pings.append(await self.four.ping)
        if config.STRING5:
            pings.append(await self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Drivers...")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_kicked()
        @self.two.on_kicked()
        @self.three.on_kicked()
        @self.four.on_kicked()
        @self.five.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.two.on_closed_voice_chat()
        @self.three.on_closed_voice_chat()
        @self.four.on_closed_voice_chat()
        @self.five.on_closed_voice_chat()
        @self.one.on_left()
        @self.two.on_left()
        @self.three.on_left()
        @self.four.on_left()
        @self.five.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler(client, update: Update):
            if not isinstance(update, StreamAudioEnded):
                return
            chat_id = update.chat_id
            await self.change_stream(client, chat_id)
            if not db.get(chat_id):
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass


Signal = Call()
