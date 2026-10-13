"""Discord formatting helpers for Clumsy Movie Bot.

This module contains deterministic helpers for Discord-facing formatting. It
intentionally does not import discord.py.
"""

DISCORD_MESSAGE_LIMIT = 2000


def chunk_lines(header, lines, max_length=DISCORD_MESSAGE_LIMIT):
    """Return message chunks that fit within Discord's message length limit.

    This preserves the existing command behavior: the header appears only in the
    first chunk, later chunks continue without repeating it, and the final chunk
    is always returned.
    """
    chunks = []
    current = header

    for line in lines:
        if len(current + line) > max_length:
            chunks.append(current)
            current = ""

        current += line

    chunks.append(current)

    return chunks
