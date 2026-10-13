"""Pause / resume the AI per chat. See userbot/handoff.py for the handoff itself."""

from telethon import events

from ..commands import Context, command
from ..handoff import PausedChats, parse_chat_id


async def _target_chat(event: events.NewMessage.Event, args: str | None) -> tuple[int | None, bool]:
    """(chat ID, whether the command was typed in that chat itself).

    The chat is the ID given as argument, else the one in a replied-to handoff
    alert, else the chat the command was typed in (unless that's Saved Messages).
    """
    if args:
        try:
            return int(args.strip()), False
        except ValueError:
            return None, False
    reply = await event.get_reply_message() if event.is_reply else None
    from_alert = parse_chat_id(reply.raw_text) if reply is not None else None
    if from_alert is not None:
        return from_alert, False
    if event.chat_id == (await event.client.get_me()).id:
        return None, False  # Saved Messages
    return event.chat_id, True


async def _answer(event: events.NewMessage.Event, text: str, in_their_chat: bool) -> None:
    # In someone's chat the command must not linger: they'd see it. Delete it instead.
    if in_their_chat:
        await event.delete()
    else:
        await event.edit(text)


@command("pause", "Stop the AI answering in this chat (or .pause <chat id>)")
async def pause(event: events.NewMessage.Event, ctx: Context) -> None:
    chat_id, here = await _target_chat(event, event.pattern_match.group(1))
    if chat_id is None:
        await event.edit("Use .pause in the chat, or .pause <chat id>.")
        return
    PausedChats(ctx.config.paused_chats_file).pause(chat_id, reason="paused by you")
    await _answer(event, f"Paused: the AI no longer answers chat {chat_id}.", here)


@command("resume", "Let the AI answer this chat again (or .resume <chat id>, or reply to a handoff alert)")
async def resume(event: events.NewMessage.Event, ctx: Context) -> None:
    chat_id, here = await _target_chat(event, event.pattern_match.group(1))
    if chat_id is None:
        await event.edit("Use .resume in the chat, .resume <chat id>, or reply .resume to a handoff alert.")
        return
    if PausedChats(ctx.config.paused_chats_file).resume(chat_id):
        await _answer(event, f"Resumed: the AI answers chat {chat_id} again.", here)
    else:
        await _answer(event, f"Chat {chat_id} wasn't paused.", here)


@command("paused", "List the chats the AI has handed over to you")
async def paused(event: events.NewMessage.Event, ctx: Context) -> None:
    text = PausedChats(ctx.config.paused_chats_file).describe()
    if event.chat_id == (await event.client.get_me()).id:
        await event.edit(text)
    else:
        # Typed in someone's chat: they mustn't see your list. Send it to Saved Messages.
        await event.delete()
        await event.client.send_message("me", text)
