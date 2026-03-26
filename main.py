import discord
from discord import app_commands
import os
import subprocess
import tempfile
import requests

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# deobfuscator.py and trace_to_lua.py are bundled in the same directory
DEOBFUSCATOR_PATH = os.path.join(os.path.dirname(__file__), "deobfuscator.py")

@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ NEW CODE V3 - Bot is online! Logged in as {bot.user}')


async def run_deobfuscator(interaction, content: str, filename: str):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "obf.lua")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)

            result = subprocess.run(
                ["python", DEOBFUSCATOR_PATH, input_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(__file__)  # important: run from repo root so trace_to_lua.py is found
            )

            # Look for .deobf.lua output
            deobf_path = None
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    if fname.endswith(".deobf.lua"):
                        deobf_path = os.path.join(root, fname)
                        break
            # Also check working dir (deobfuscator sometimes writes next to input)
            if not deobf_path:
                for root, dirs, files in os.walk(os.path.dirname(__file__)):
                    for fname in files:
                        if fname.endswith(".deobf.lua"):
                            deobf_path = os.path.join(root, fname)
                            break

            if deobf_path and os.path.exists(deobf_path):
                with open(deobf_path, "rb") as f:
                    discord_file = discord.File(f, filename="deobfuscated.lua")
                # Clean up
                try:
                    os.remove(deobf_path)
                except:
                    pass
                await interaction.followup.send(
                    f"✅ Deobfuscation successful! **File:** `{filename}`",
                    file=discord_file
                )
            else:
                log = (result.stdout + "\n" + result.stderr)[-1800:]
                await interaction.followup.send(
                    f"⚠️ Dumper ran but no output file was generated.\n```\n{log}\n```"
                )

    except subprocess.TimeoutExpired:
        await interaction.followup.send("❌ Timed out while deobfuscating.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:1900]}")


@tree.command(name="l", description="Deobfuscate WeAreDevs/Prometheus Lua from a direct link")
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
