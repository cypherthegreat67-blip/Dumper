import discord
from discord import app_commands
import os
import requests
import io
import json

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = """You are a Lua deobfuscator. Your job is to take obfuscated Lua scripts (such as WeAreDevs/Prometheus obfuscated scripts) and return clean, fully readable Lua code.

Rules:
- Decrypt all string constants and replace them with their actual values
- Rename obfuscated variable names to readable names based on context
- Remove all obfuscation layers, wrappers, and junk code
- Reconstruct the original logic as clean readable Lua
- Only output the deobfuscated Lua code, nothing else — no explanations, no markdown, no code blocks
- If the script is too large or complex, deobfuscate as much as possible and output what you can"""

def deobfuscate_with_gemini(content: str) -> str:
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Deobfuscate this Lua script:\n\n" + content}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 8192
        }
    }

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=120
    )

    if not response.ok:
        raise Exception(f"Gemini API error {response.status_code}: {response.text[:500]}")

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot is online! Logged in as {bot.user}')


async def send_result(channel, result: str):
    # Strip markdown code blocks if Gemini adds them
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0].strip()

    if len(result) > 1900:
        file = discord.File(io.BytesIO(result.encode("utf-8")), filename="deobfuscated.lua")
        await channel.send("✅ Deobfuscation complete!", file=file)
    else:
        await channel.send(f"✅ Deobfuscation complete!\n```lua\n{result}\n```")


@tree.command(name="l", description="Deobfuscate Lua from a direct link")
@app_commands.describe(link="Direct raw link to .lua or .txt file")
async def deobf_link(interaction: discord.Interaction, link: str):
    if not link.startswith("http"):
        await interaction.response.send_message("❌ Please provide a valid direct link (http/https)", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        r = requests.get(link, timeout=20)
        r.raise_for_status()
        content = r.text
    except requests.exceptions.RequestException:
        await interaction.followup.send("❌ Failed to download the file. Make sure it's a **direct raw** link.")
        return

    try:
        await interaction.followup.send("⏳ Deobfuscating, please wait...")
        result = deobfuscate_with_gemini(content)
        await send_result(interaction.channel, result)
    except Exception as e:
        await interaction.channel.send(f"❌ Error: {str(e)[:1900]}")


@tree.command(name="f", description="Deobfuscate Lua from an uploaded file")
@app_commands.describe(file="Upload a .lua or .txt file to deobfuscate")
async def deobf_file(interaction: discord.Interaction, file: discord.Attachment):
    if not (file.filename.endswith(".lua") or file.filename.endswith(".txt")):
        await interaction.response.send_message("❌ Please upload a `.lua` or `.txt` file.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        content = (await file.read()).decode("utf-8")
    except Exception:
        await interaction.followup.send("❌ Failed to read the uploaded file.")
        return

    try:
        await interaction.followup.send("⏳ Deobfuscating, please wait...")
        result = deobfuscate_with_gemini(content)
        await send_result(interaction.channel, result)
    except Exception as e:
        await interaction.channel.send(f"❌ Error: {str(e)[:1900]}")


if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Please set the TOKEN environment variable!")
    else:
        bot.run(token)
