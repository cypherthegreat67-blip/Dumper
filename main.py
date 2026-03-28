import discord
from discord import app_commands
import os
import requests
import subprocess
import tempfile
import io

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Path to the deobfuscator cli
DEOB_CLI = os.path.join(os.path.dirname(__file__), "deobfuscator", "src", "deob", "cli.lua")


async def run_deobfuscator(interaction, content: str, filename: str):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.lua")
            output_path = os.path.join(tmpdir, "output.deob.lua")

            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)

            result = subprocess.run(
                ["lua5.1", DEOB_CLI, input_path, "--out", output_path, "--trace", "calls"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(__file__)
            )

            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8", errors="replace") as f:
                    deobfed = f.read()

                if len(deobfed) > 1900:
                    file = discord.File(io.BytesIO(deobfed.encode("utf-8")), filename="deobfuscated.lua")
                    await interaction.channel.send("✅ Deobfuscation complete!", file=file)
                else:
                    await interaction.channel.send(f"✅ Deobfuscation complete!\n```lua\n{deobfed}\n```")
            else:
                log = (result.stdout + "\n" + result.stderr)[-1800:]
                await interaction.channel.send(f"⚠️ No output file generated.\n```\n{log}\n```")

    except subprocess.TimeoutExpired:
        await interaction.channel.send("❌ Timed out while deobfuscating.")
    except Exception as e:
        await interaction.channel.send(f"❌ Error: {str(e)[:1900]}")


@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot is online! Logged in as {bot.user}')


@tree.command(name="l", description="Deobfuscate Prometheus/WeAreDevs Lua from a direct link")
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

    await interaction.followup.send("⏳ Deobfuscating, please wait...")
    await run_deobfuscator(interaction, content, link.split("/")[-1])


@tree.command(name="f", description="Deobfuscate Prometheus/WeAreDevs Lua from an uploaded file")
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

    await interaction.followup.send("⏳ Deobfuscating, please wait...")
    await run_deobfuscator(interaction, content, file.filename)


if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Please set the TOKEN environment variable!")
    else:
        bot.run(token)
