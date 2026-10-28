import os
import asyncio
import base64
import logging
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("chamak-ai")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
PORT = int(os.getenv("PORT", "10000"))

SYSTEM_PROMPT = """
You are CHAMAK AI, a helpful, friendly assistant.
Reply in simple Hinglish/Hindi when the user writes in Hindi or Hinglish;
otherwise reply in the user's language. Be accurate and concise.
If unsure, say so. Do not invent facts. For scripts, give clear,
copy-ready formatting. You can describe uploaded images, but do not claim
to create or send a video unless a separate video-generation service is configured.
"""

# Store only text history; do not keep large image data in memory.
chat_history = defaultdict(list)
MAX_HISTORY_MESSAGES = 12

client = OpenAI(
    api_key=GEMINI_API_KEY or "missing-api-key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    timeout=45.0,
    max_retries=0,
)


def generate_reply(history, user_text, image_data_url=None):
    """Synchronous API call; called through asyncio.to_thread."""
    if not GEMINI_API_KEY:
        return (
            "CHAMAK AI setup incomplete hai: Render Environment mein "
            "GEMINI_API_KEY add karo, phir redeploy karo."
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-MAX_HISTORY_MESSAGES:])

    if image_data_url:
        content = [
            {"type": "text", "text": user_text or "Is image ko detail mein samjhao."},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_text})

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                max_tokens=1200,
            )
            answer = response.choices[0].message.content
            if isinstance(answer, str) and answer.strip():
                return answer.strip()
            return "Is baar AI se khaali jawab aaya. Ek baar phir try karo."

        except Exception as exc:
            error_text = str(exc).lower()
            status_code = getattr(exc, "status_code", None)
            logger.exception("Gemini request failed (attempt %s)", attempt + 1)

            # A quota-exhausted response will not be fixed by retrying.
            if (
                status_code == 429
                or "resource_exhausted" in error_text
                or "quota" in error_text
                or "rate limit" in error_text
            ):
                return (
                    "Gemini API ki free quota/limit abhi khatam hai. "
                    "Thodi der baad try karo ya Google AI Studio mein quota "
                    "check karo. Is waqt code se quota bypass nahi ho sakta."
                )

            if attempt == 0 and (
                status_code == 503
                or "503" in error_text
                or "service unavailable" in error_text
                or "timeout" in error_text
            ):
                time.sleep(1.5)
                continue

            if status_code == 401 or "api key" in error_text or "unauthorized" in error_text:
                return (
                    "Gemini API key reject hui. Render → Environment mein "
                    "GEMINI_API_KEY check karo, phir redeploy karo."
                )

            if status_code == 404 or "not_found" in error_text or "not found" in error_text:
                return (
                    f"Gemini model '{GEMINI_MODEL}' available nahi lag raha. "
                    "Render Environment mein GEMINI_MODEL ko Google AI Studio "
                    "mein listed supported model se match karo."
                )

            return (
                "AI service se abhi response nahi mila. Render Logs mein "
                "latest error check karo aur thodi der baad try karo."
            )

    return "Gemini service abhi busy hai. Thodi der baad dobara try karo."


async def send_long_message(update: Update, text: str):
    if not update.effective_message:
        return
    # Telegram messages have a length limit; split long responses safely.
    for start in range(0, len(text), 3900):
        await update.effective_message.reply_text(text[start:start + 3900])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(
            "Namaste! Main CHAMAK AI hoon. 🤖\n\n"
            "Mujhe text bhejo ya koi photo bhejkar uske baare mein poochho.\n"
            "/reset — chat history clear karne ke liye\n"
            "/help — help dekhne ke liye"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(
            "CHAMAK AI Help\n\n"
            "• Normal text bhejo — AI jawab dega.\n"
            "• Photo bhejo — photo ke baare mein sawaal pooch sakte ho.\n"
            "• /reset — current chat ki history clear karega.\n\n"
            "Note: Text/image understanding configured hai. Video generation "
            "ke liye alag video-generation API/service chahiye."
        )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is not None:
        chat_history.pop(chat_id, None)
    if update.effective_message:
        await update.effective_message.reply_text("Chat history clear ho gayi. Nayi chat shuru karo! ✅")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not message.text:
        return

    user_text = message.text.strip()
    if not user_text:
        return

    await message.reply_chat_action("typing")
    history = list(chat_history[chat.id])
    answer = await asyncio.to_thread(generate_reply, history, user_text, None)

    # Keep conversation context only for successful AI responses.
    if not answer.startswith(("Gemini API ki free quota", "Gemini model '", "Gemini API key", "AI service")):
        chat_history[chat.id].extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ])
        chat_history[chat.id] = chat_history[chat.id][-MAX_HISTORY_MESSAGES:]

    await send_long_message(update, answer)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not message.photo:
        return

    await message.reply_chat_action("typing")
    try:
        photo_file = await message.photo[-1].get_file()
        photo_bytes = bytes(await photo_file.download_as_bytearray())
        image_data_url = "data:image/jpeg;base64," + base64.b64encode(photo_bytes).decode("ascii")
    except Exception:
        logger.exception("Photo download failed")
        await message.reply_text("Photo download nahi ho paya. Ek baar dobara bhejo.")
        return

    prompt = (message.caption or "").strip() or "Is photo mein kya dikh raha hai? Hinglish mein detail se batao."
    history = list(chat_history[chat.id])
    answer = await asyncio.to_thread(generate_reply, history, prompt, image_data_url)

    if not answer.startswith(("Gemini API ki free quota", "Gemini model '", "Gemini API key", "AI service")):
        chat_history[chat.id].extend([
            {"role": "user", "content": "[Photo] " + prompt},
            {"role": "assistant", "content": answer},
        ])
        chat_history[chat.id] = chat_history[chat.id][-MAX_HISTORY_MESSAGES:]

    await send_long_message(update, answer)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Telegram handler error: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Bot mein temporary error aa gaya. Thodi der baad phir try karo."
            )
        except Exception:
            logger.exception("Could not send error message")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"CHAMAK AI is alive")

    def log_message(self, format, *args):
        # Keep Render logs focused on useful application messages.
        return


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health server listening on port %s", PORT)


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Missing TELEGRAM_TOKEN. Add it in Render Environment.")
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is missing; bot will explain setup to users.")

    start_health_server()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    logger.info("Starting CHAMAK AI polling. Model: %s", GEMINI_MODEL)
    # Run only ONE polling instance for this Telegram bot token.
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
