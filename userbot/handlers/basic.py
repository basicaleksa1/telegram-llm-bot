"""Example commands. Send them from your own account, e.g. in "Saved Messages"."""

import time

from telethon import events

from ..commands import Context, command


@command("ping", "Check that the userbot is alive and measure latency")
async def ping(event: events.NewMessage.Event, ctx: Context) -> None:
    start = time.perf_counter()
    await event.edit("pong")
    elapsed_ms = (time.perf_counter() - start) * 1000
    await event.edit(f"pong ({elapsed_ms:.0f} ms)")


@command("id", "Show the chat ID (and the sender's ID when used as a reply)")
async def chat_id(event: events.NewMessage.Event, ctx: Context) -> None:
    lines = [f"Chat ID: {event.chat_id}"]
    reply = await event.get_reply_message()
    if reply is not None:
        lines.append(f"Replied-to sender ID: {reply.sender_id}")
        lines.append(f"Replied-to message ID: {reply.id}")
    await event.edit("\n".join(lines))


@command("help", "List available commands")
async def help_(event: events.NewMessage.Event, ctx: Context) -> None:
    await event.edit(format_help(ctx))


def format_help(ctx: Context) -> str:
    prefix = ctx.config.command_prefix
    lines = ["Available commands:"]
    lines += [f"{prefix}{cmd.name} - {cmd.description}" for cmd in ctx.commands]
    return "\n".join(lines)
