import os
import logging
import discord
import feedparser
import asyncio
import re
from discord.ext import commands, tasks
from .utils import send_to_discord, get_role_mention
from .logging_config import setup_logging
from .commands import setup as setup_commands
from lib.http.db_utils import fetch_pending_entries, delete_pending_entry, get_last_entry_id, delete_old_entries, entry_already_processed, save_processed_entry  # Import fungsi dari db_utils
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()

# Inisialisasi bot dengan AutoShardedBot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.AutoShardedBot(command_prefix='!', intents=intents)

# Setup custom commands
setup_commands(bot)

# Fungsi untuk mengambil feed menggunakan run_in_executor
async def fetch_feed(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, feedparser.parse, url)

# Fungsi untuk mengambil feed dengan retry logic
async def fetch_feed_with_retry(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return await fetch_feed(url)
        except Exception as e:
            logging.error(f"Error fetching feed (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                raise

@tasks.loop(minutes=2)
async def check_pending_entries():
    logging.info("Checking for pending entries...")
    pending_entries = fetch_pending_entries()
    for entry in pending_entries:
        entry_id, published, title, link, author = entry
        role_mention = await get_role_mention(bot, title)
        if role_mention:
            await send_to_discord(bot, entry_id, title, link, published, author)
            delete_pending_entry(entry_id)
            delete_old_entries()
        # else:
            # logging.info(f"Role for '{title}' not found yet. Will retry later.")

def extract_series_name(title):
    # Misalnya, kita anggap nama seri adalah bagian dari judul sebelum "Chapter" atau "Episode"
    match = re.match(r'^(.*?)(?:Chapter \d+|Episode \d+)?$', title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return title

# Fungsi untuk memeriksa apakah entry sudah ada di dalam daftar drop menggunakan message_id
async def is_entry_in_drop_list(channel, message_id, title):
    try:
        # Mendapatkan pesan spesifik berdasarkan message_id
        message = await channel.fetch_message(message_id)
        
        # Ekstrak nama seri dari title
        extracted_title = extract_series_name(title).lower()
        
        # Periksa apakah nama seri yang telah diekstrak ada di dalam konten pesan
        if extracted_title in message.content.lower():
            return True
        
    except discord.NotFound:
        logging.error(f"Message with ID {message_id} not found.")
    except discord.Forbidden:
        logging.error(f"Bot does not have permission to fetch message with ID {message_id}.")
    except discord.HTTPException as e:
        logging.error(f"HTTPException occurred: {e}")

    return False


# Fungsi untuk memeriksa feed dan mengirim update
@tasks.loop(minutes=2)
async def check_feed():
    try:
        logging.info('Checking feed...')
        new_feed = await asyncio.wait_for(fetch_feed_with_retry(os.getenv('RSS_URL')), timeout=60)
        last_entry_id = get_last_entry_id()

        # Tentukan channel dan message_id di mana list project drop diposting
        drop_channel_id = int(os.getenv('CHANNEL_DROP_ID'))  # Pastikan ID channel diparsing sebagai integer
        drop_message_id = int(os.getenv('MESSAGE_DROP_ID'))  # Pastikan ID pesan diparsing sebagai integer
        
        drop_channel = bot.get_channel(drop_channel_id)

        if drop_channel is None:
            logging.error(f"Channel with ID {drop_channel_id} not found.")
            return

        # Iterate through all entries in the feed
        for entry in new_feed.entries:
            if not entry_already_processed(entry.id):
                title = entry.title
                link = entry.link
                author = entry.author
                published = entry.published

                # Cek apakah entry sudah ada di list project drop
                if await is_entry_in_drop_list(drop_channel, drop_message_id, title):
                    logging.info(f"Entry '{title}' ditemukan di daftar drop, tidak akan dikirim.")
                    continue

                save_processed_entry(entry.id, published, title, link, author)

                logging.info(f"New entry found: {title}")

                await send_to_discord(bot, entry.id, title, link, published, author)
                logging.info(f"Successfully sent notification for: {title}")

    except asyncio.TimeoutError:
        logging.error('Timeout while fetching the feed')
    except Exception as e:
        logging.error(f"Error checking feed: {e}")

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user.name}')
    if not check_feed.is_running():
        check_feed.start()  # Mulai pengecekan feed secara berkala jika belum berjalan

    if not check_pending_entries.is_running():
        check_pending_entries.start()  # Mulai pengecekan entri yang tertunda secara berkala jika belum berjalan

bot.run(os.getenv('DISCORD_TOKEN'))
