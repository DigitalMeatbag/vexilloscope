import asyncio
import os
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import discord
from discord import app_commands
from PIL import Image as PILImage

TOKEN   = os.environ["Vexilloscope_DiscordToken"]
EXE     = os.environ.get("VEXILLOSCOPE_EXE",     str(Path(__file__).parent.parent / "build" / "vexilloscope.exe"))
WEIGHTS = os.environ.get("VEXILLOSCOPE_WEIGHTS",  str(Path(__file__).parent.parent / "vit_weights.bin"))

DEBUG_DIR = Path(__file__).parent / "debug"

RESULT_RE = re.compile(r"#(\d+)\s+(\S+)\s+(.+?)\s+logit:\s+([-\d.]+)")


def flag_emoji(code: str) -> str:
    if len(code) == 2:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())
    return ""  # sub-national codes (GB-ENG etc.) have no standard Unicode flag emoji

client = discord.Client(intents=discord.Intents.default())
tree   = app_commands.CommandTree(client)


def _run_identify(tmp_path: str) -> tuple[str, str, str]:
    """Returns (parsed_result, raw_stdout, raw_stderr)."""
    result = subprocess.run(
        [EXE, "--identify", tmp_path, "--weights", WEIGHTS],
        capture_output=True, text=True, timeout=30,
        cwd=str(Path(__file__).parent.parent),
    )

    if result.returncode != 0:
        return (
            f"error: {result.stderr.strip() or 'classifier exited non-zero'}",
            result.stdout,
            result.stderr,
        )

    lines = []
    for line in result.stdout.splitlines():
        m = RESULT_RE.search(line)
        if m:
            rank, code, name, logit = m.groups()
            emoji = flag_emoji(code)
            prefix = f"{emoji} " if emoji else ""
            lines.append(f"{rank}. {prefix}**{name.strip()}** ({code})  —  logit {float(logit):.2f}")

    parsed = "\n".join(lines) if lines else "no results returned"
    return parsed, result.stdout, result.stderr


def _preprocess(data: bytes) -> tuple[bytes, tuple[int, int], str]:
    """Normalize any image format to a 128×128 RGB PNG composited against white.
    Returns (png_bytes, original_size, original_format)."""
    img = PILImage.open(BytesIO(data))
    fmt = img.format or "unknown"
    original_size = img.size
    img = img.convert("RGBA")
    bg  = PILImage.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    out = bg.convert("RGB").resize((128, 128), PILImage.LANCZOS)
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue(), original_size, fmt


async def identify_attachment(attachment: discord.Attachment) -> str:
    print(f"  attachment: {attachment.filename}  content_type={attachment.content_type}  size={attachment.size}B")

    data = await attachment.read()
    print(f"  downloaded: {len(data)}B")

    png_data, original_size, fmt = _preprocess(data)
    print(f"  preprocessed: format={fmt}  original={original_size}  → 128×128 PNG ({len(png_data)}B)")

    DEBUG_DIR.mkdir(exist_ok=True)
    debug_path = DEBUG_DIR / "last_input.png"
    debug_path.write_bytes(png_data)
    print(f"  debug image saved: {debug_path}")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_data)
        tmp_path = tmp.name

    try:
        parsed, stdout, stderr = await asyncio.to_thread(_run_identify, tmp_path)
        print(f"  stdout:\n{stdout.rstrip()}")
        if stderr.strip():
            print(f"  stderr:\n{stderr.rstrip()}")
        return parsed
    finally:
        os.unlink(tmp_path)


@tree.context_menu(name="Identify flag")
async def identify_flag(interaction: discord.Interaction, message: discord.Message):
    images = [
        a for a in message.attachments
        if a.content_type and a.content_type.startswith("image/")
    ]

    if not images:
        await interaction.response.send_message(
            "No image found in that message.", ephemeral=True
        )
        return

    print(f"identify requested by {interaction.user} for message {message.id}")
    await interaction.response.defer()

    try:
        result = await identify_attachment(images[0])
        await interaction.followup.send(f"**Flag identification:**\n{result}")
    except asyncio.TimeoutError:
        await interaction.followup.send("timed out running classifier — try again")
    except Exception as e:
        print(f"  exception: {e}")
        await interaction.followup.send(f"error: {e}")


@client.event
async def on_ready():
    await tree.sync()
    print(f"ready: {client.user} (id: {client.user.id})")
    print(f"  exe:     {EXE}")
    print(f"  weights: {WEIGHTS}")


client.run(TOKEN)
