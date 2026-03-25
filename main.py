import discord
from discord import app_commands
import os
import subprocess
import tempfile
import requests
import zipfile
import io

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

DEOBFUSCATOR_REPO = "https://github.com/hutaoshusband/Prometheus-WeAre-Devs-Dumper.git"
DEOBFUSCATOR_DIR = "Prometheus-WeAre-Devs-Dumper"
DEOBFUSCATOR_PATH = os.path.join(DEOBFUSCATOR_DIR, "deobfuscator.py")

def ensure_deobfuscator():
    """Clone the deobfuscator repo using git, or fall back to downloading the zip."""
    if os.path.exists(DEOBFUSCATOR_DIR):
        return  # Already downloaded

    # Try git first
    git_available = subprocess.run(
        ["git", "--version"],
        capture_output=True
    ).returncode == 0

    if git_available:
        subprocess.run(["git", "clone", DEOBFUSCATOR_REPO], check=True, timeout=60)
    else:
        # Fallback: download zip from GitHub
        print("git not found, falling back to zip download...")
        zip_url = "https://github.com/hutaoshusband/Prometheus-WeAre-Devs-Dumper/archive/refs/heads/main.zip"
        r = requests.get(zip_url, timeout=30)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(".")
        # GitHub zips extract as RepoName-main, rename to expected dir
        extracted = "Prometheus-WeAre-Devs-Dumper-main"
        if os.path.exists(extracted):
            os.rename(extracted, DEOBFUSCATOR_DIR)


async def run_deobfuscator(interaction, content: str, filename: str):
    """Core logic: run the deobfuscator on given Lua content and reply."""
    try:
        ensure_deobfuscator()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "obf.lua")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)

            result = subprocess.run(
                ["python", DEOBFUSCATOR_PATH, input_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Search for output file
            deobf_path = None
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    if fname.endswith(".lua") and fname != "obf.lua":
                        deobf_path = os.path.join(root, fname)
                        break
                if deobf_path:
                    break

            if deobf_path and os.path.exists(deobf_path):
                with open(deobf_path, "rb") as f:
                    discord_file = discord.File(f, filename="deobfuscated.lua")
                await interaction.followup.send(
                    f"✅ Deobfuscation successful! **File:** `{filename}`",
                    file=discord_file
                )
            else:
                log = (result.stdout + "\n" + result.stderr)[-1800:]
                await interaction.followup.send(
                    f"⚠️ Dumper ran but no output file was generated.\n```ansi\n{log}\n```"
                )

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:1900]}")


@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot is online! Logged in as {bot.user}')


@tree.command(name="l", description="Deobfuscate WeAreDevs/Prometheus Lua from a direct link")
@app_commands.describe(link="Direct raw link to .lua or .txt file")
async def deobf_link(interaction: discord.Interaction, link: str):
    if not link.startswith("http"):
        await interaction.response.send_message("❌ Please provide a valid direct link (http/https)", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        print(f"Downloading from: {link}")
        r = requests.get(link, timeout=20)
        r.raise_for_status()
        content = r.text
    except requests.exceptions.RequestException:
        await interaction.followup.send("❌ Failed to download the file. Make sure it's a **direct raw** link.")
        return

    await run_deobfuscator(interaction, content, link.split("/")[-1])


@tree.command(name="f", description="Deobfuscate WeAreDevs/Prometheus Lua from an uploaded file")
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

    await run_deobfuscator(interaction, content, file.filename)


if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ Please set the TOKEN environment variable!")
