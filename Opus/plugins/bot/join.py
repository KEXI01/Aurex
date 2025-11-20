from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, ChatWriteForbidden
from Opus import app 

MUST_JOIN_CHANNEL = "Syphixlabs"
SUPPORT_GROUP = "SyphixHub"

async def check_user_membership(client: Client, user_id: int, chat_id: str) -> bool:
    try:
        await client.get_chat_member(chat_id, user_id)
        return True
    except UserNotParticipant:
        return False
    except ChatAdminRequired:
        print(f"⚠️ ʙᴏᴛ ɪꜱ ɴᴏᴛ ᴀᴅᴍɪɴ ɪɴ: {chat_id}")
        return True  
        
def get_invite_link(username: str) -> str:
    return f"https://t.me/{username}"

async def send_force_join_message(client: Client, user_id: int, old_msg_id: int = None):
    need_channel = not await check_user_membership(client, user_id, MUST_JOIN_CHANNEL)
    need_group = not await check_user_membership(client, user_id, SUPPORT_GROUP)

    if need_channel or need_group:
        buttons = []
        if need_channel:
            buttons.append(InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=get_invite_link(MUST_JOIN_CHANNEL)))
        if need_group:
            buttons.append(InlineKeyboardButton("💬 ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ", url=get_invite_link(SUPPORT_GROUP)))
        keyboard = [buttons] if buttons else []
        keyboard.append([InlineKeyboardButton("🔄", callback_data="check_joined")])

        if old_msg_id:
            try:
                await client.delete_messages(chat_id=user_id, message_ids=old_msg_id)
            except:
                pass

        await client.send_message(
            chat_id=user_id,
            text="<blockquote><b>» ᴛᴏ ᴜꜱᴇ ᴍʏ ꜰᴇᴀᴛᴜʀᴇꜱ, ʏᴏᴜ ᴍᴜꜱᴛ ᴊᴏɪɴ ʙᴏᴛʜ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴀɴᴅ ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ.</b></blockquote>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        return True
    return False

@app.on_message(filters.incoming & filters.private, group=-1)
async def must_join_handler(client: Client, msg: Message):
    try:
        blocked = await send_force_join_message(client, msg.from_user.id)
        if blocked:
            await msg.stop_propagation()
    except ChatWriteForbidden:
        pass

@app.on_callback_query(filters.regex("check_joined"))
async def recheck_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    msg = callback_query.message

    blocked = await send_force_join_message(client, user.id, old_msg_id=msg.id)

    if not blocked:
        try:
            await client.delete_messages(chat_id=user.id, message_ids=msg.id)
        except:
            pass
        await client.send_message(
            chat_id=user.id,
            text="<blockquote><b>✅ ʏᴏᴜ ʜᴀᴠᴇ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴊᴏɪɴᴇᴅ ʙᴏᴛʜ! ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜꜱᴇ ᴛʜᴇ ʙᴏᴛ.</b></blockquote>"
        )
