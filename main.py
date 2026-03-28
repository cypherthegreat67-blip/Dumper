import discord
from discord import app_commands
import os
import requests
import io

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT = """You are a Lua deobfuscator. Your job is to take obfuscated Lua scripts (such as WeAreDevs/Prometheus obfuscated scripts) and return clean, fully readable Lua code.

Rules:
- Decrypt all string constants and replace them with their actual values
- Rename obfuscated variable names to readable names based on context
- Remove all obfuscation layers, wrappers, and junk code
- Reconstruct the original logic as clean readable Lua
- Only output the deobfuscated Lua code, nothing else — no explanations, no markdown, no code blocks
- If the script is too large or complex, deobfuscate as much as possible and output what you can"""

def deobfuscate_with_groq(content: str) -> str:
    if len(content) > 50000:
        content = content[:50000]

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": 8096,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Deobfuscate this Lua script:\n\n{content}"}
            ]
        },
        timeout=120
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot is online! Logged in as {bot.user}')


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
        result = deobfuscate_with_groq(content)

        if len(result) > 1900:
            file = discord.File(io.BytesIO(result.encode()), filename="deobfuscated.lua")
            await interaction.channel.send("✅ Deobfuscation complete!", file=file)
        else:
            await interaction.channel.send(f"✅ Deobfuscation complete!\n```lua\n{result}\n```")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:1900]}")


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
        result = deobfuscate_with_groq(content)

        if len(result) > 1900:
            file_out = discord.File(io.BytesIO(result.encode()), filename="deobfuscated.lua")
            await interaction.channel.send("✅ Deobfuscation complete!", file=file_out)
        else:
            await interaction.channel.send(f"✅ Deobfuscation complete!\n```lua\n{result}\n```")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:1900]}")


if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Please set the TOKEN environment variable!")
    else:
        bot.run(token)
