import discord
from discord import app_commands
import os
import subprocess
import tempfile
import requests

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

DEOBFUSCATOR_REPO = "https://github.com/hutaoshusband/Prometheus-WeAre-Devs-Dumper.git"
DEOBFUSCATOR_DIR = "Prometheus-WeAre-Devs-Dumper"
DEOBFUSCATOR_PATH = os.path.join(DEOBFUSCATOR_DIR, "deobfuscator.py")

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
        # Download the script from link
        print(f"Downloading from: {link}")
        r = requests.get(link, timeout=20)
        r.raise_for_status()
        content = r.text

        # Clone dumper if missing
        if not os.path.exists(DEOBFUSCATOR_DIR):
            print("Cloning deobfuscator repo...")
            subprocess.run(["git", "clone", DEOBFUSCATOR_REPO], check=True, timeout=30)

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "obf.lua")
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Run the dumper
            result = subprocess.run(
                ["python", DEOBFUSCATOR_PATH, input_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Find the deobfuscated output (usually creates .deobf.lua or in unobfuscated_scripts, but we search)
            deobf_path = None
            for root, dirs, files in os.walk(tmpdir):
                for filename in files:
                    if filename.endswith(".lua") and ("deobf" in filename.lower() or filename != "obf.lua"):
                        deobf_path = os.path.join(root, filename)
                        break
                if deobf_path:
                    break

            # Fallback: check if trace_to_lua produced something or use report
            if not deobf_path or not os.path.exists(deobf_path):
                # Many times it creates filename.report.txt and trace_to_lua can help, but for simplicity we check for any new .lua
                for root, dirs, files in os.walk(tmpdir):
                    for f in files:
                        if f.endswith(".lua") and f != "obf.lua":
                            deobf_path = os.path.join(root, f)
                            break

            if deobf_path and os.path.exists(deobf_path):
                with open(deobf_path, "rb") as f:
                    discord_file = discord.File(f, filename="deobfuscated.lua")
                await interaction.followup.send(
                    f"✅ Deobfuscation successful!\n**Link:** {link}",
                    file=discord_file
                )
            else:
                # Send console output for debugging
                log = (result.stdout + "\n" + result.stderr)[-1800:]
                await interaction.followup.send(
                    f"⚠️ Dumper ran but no clean file was generated.\nCheck the logs below:\n```ansi\n{log}\n```"
                )

    except requests.exceptions.RequestException:
        await interaction.followup.send("❌ Failed to download the file from the link. Make sure it's a **direct raw** link.")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)[:1900]}")

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ Please set the TOKEN environment variable!")
