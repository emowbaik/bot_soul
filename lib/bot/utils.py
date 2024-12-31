import os
from datetime import datetime
from dateutil import parser
import discord
import logging
import re
from fuzzywuzzy import fuzz
from lib.http.db_utils import save_pending_entry

# Fungsi untuk mengubah warna hex menjadi integer
def hex_to_int(hex_color):
    return int(hex_color.lstrip('#'), 16)

# Fungsi untuk menyederhanakan timestamp
def simplify_timestamp(timestamp):
    # Jika timestamp adalah objek datetime, ubah menjadi string
    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()  # Mengubah datetime menjadi string ISO
    try:
        dt = parser.parse(timestamp)
        return dt.strftime('%d %B %Y, %H:%M %p')
    except Exception as e:
        logging.error(f"Failed to simplify timestamp: {e}")
        return "Invalid date"

# Fungsi untuk mengekstrak nama seri dari judul
def extract_series_name(title):
    # Misalnya, kita anggap nama seri adalah bagian dari judul sebelum "Chapter" atau "Episode"
    match = re.match(r'^(.*?)(?:Chapter \d+|Episode \d+)?$', title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return title

# Fungsi untuk menentukan role mention berdasarkan title dari RSS feed
async def get_role_mention(bot, title):
    series_name = extract_series_name(title)
    guild = bot.get_guild(int(os.getenv('GUILD_ID')))

    if not guild:
        logging.error("Guild not found.")
        return ""

    # Ambil semua role dari guild
    roles = guild.roles

    # Inisialisasi nilai awal
    best_match = None
    highest_score = 0

    for role in roles:
        # Skip roles with only one word
        if len(role.name.split()) == 1:
            continue

        # Hitung skor kecocokan menggunakan fuzzy matching
        score = fuzz.partial_ratio(series_name.lower(), role.name.lower())
        if score > highest_score:
            highest_score = score
            best_match = role

    # Hanya mengembalikan role yang memiliki skor lebih dari 8
    if best_match and highest_score > 80:
        return best_match.mention

    # logging.error(f"Role containing keywords from '{series_name}' not found in guild.")
    return ""

# Fungsi untuk mengirim pesan ke Discord dengan dua tombol
async def send_to_discord(bot, entry_id, title, link, published, author):
    role_mention = await get_role_mention(bot, title)

    # channel = bot.get_channel(channel_id)  # Mengambil channel berdasarkan ID
    # if channel:
    #     message = f"**{title}**\nLink: {link}\nPublished: {published}\nAuthor: {author}"
    #     await channel.send(message)
    #     logging.info(f"Message sent to channel ID {channel_id}: {message}")
    # else:
    #     logging.error(f"Channel with ID {channel_id} not found")
    
    if not role_mention:
        save_pending_entry(entry_id, published, title, link, author)
        return
    
    simplified_time = simplify_timestamp(published)
    embed = discord.Embed(
        title=title,
        color=hex_to_int("#D58D34")
    )
    embed.set_footer(text=f"Posted by {author} • {simplified_time}")

    button1 = discord.ui.Button(label="Baca Sekarang", url=link, style=discord.ButtonStyle.link)
    button2 = discord.ui.Button(label="Visit Site", url="https://soulscans.my.id/", style=discord.ButtonStyle.link)

    view = discord.ui.View()
    view.add_item(button1)
    view.add_item(button2)

    channel = bot.get_channel(int(os.getenv('CHANNEL_ID')))
    if channel:
        try:
            await channel.send(content=f"<@&1109354321033826365> | {role_mention} Read Now!", embed=embed, view=view)
        except discord.DiscordException as e:
            logging.error(f"Failed to send message: {e}")
    else:
        logging.error("Channel not found.")
