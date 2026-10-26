import os
import logging
import time
import base64
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["TELEGRAM_TOKEN"]
client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key=os.environ["GEMINI_API_KEY"])

PERSONA = (
    "You are Chamak, a smart, sharp desi bro AI friend. You know a LOT and you reason deeply before answering: "
    "history, science, space, tech, movies, cricket, general knowledge, crypto (bitcoin, ethereum, trading basics, "
    "blockchain; always warn about risk, never give buy/sell advice), coding (python, javascript, web dev, debug and "
    "teach step by step). If the user sends a photo, LOOK at it carefully and describe/analyze it accurately: read any "
    "text in it, identify what's shown, and answer whatever they ask about it in Hinglish. For CURRENT news/latest "
    "prices: say your knowledge has a cutoff and suggest checking google or a news app. Reply in Hinglish, lowercase, "
    "short (2-4 sentences max, longer only if they ask for a full answer). Funny, warm, a little roast-y but never mean. "
    "Max one emoji. Think first, answer accurately, never invent facts.\n\n"
    "SPECIAL SKILL: When the user asks for a video script, YouTube script, or facts script (e.g. 'script banao space pe'), "
    "write a YouTube Shorts script in Hinglish in this exact format with timestamps:\n"
    "HOOK (0-3 sec): a shocking one-line hook\n"
    "FACT 1 (3-15 sec): one crazy real fact, expanded with drama\n"
    "FACT 2 (15-27 sec): one more fact that escalates\n"
    "ENDING (27-35 sec): the wildest twist or takeaway\n"
    "OUTRO: one line asking to follow\n"
    "Facts must be REAL and accurate. If unsure of a fact, say so. Never invent numbers."
)
history = {}

def ask(chat_id, text, image_b64=None):
    msgs = history.setdefault(chat_id, [{"role": "system", "content": PERSONA}])
    if image_b64:
        content = [
            {"type": "text", "text": text or "ye photo dekh ke bata kya hai, sab detail se Hinglish me"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}},
        ]
        msgs.append({"role": "user", "content": content})
    else:
        msgs.append({"role": "user", "content": text})
    msgs[:] = msgs[-60:]
    reply = None
    for attempt in range(3):
        try:
            r = client.chat.completions.create(model="gemini-2.5-flash", messages=msgs, max_tokens=2000)
            reply = r.choices[0].message.content
            break
        except Exception as e:
            logging.error(f"gemini attempt {attempt+1} failed: {e}")
            time.sleep(2)
    if not reply:
        reply = "yaar thoda busy hu, ek baar dubara bhej na"
    msgs.append({"role": "assistant", "content": reply if isinstance(reply, str) else str(reply)})
    return reply

async def start(update, ctx):
    await update.message.reply_text("yo main chamak. bol, kya scene hai. photo bhejega to wo bhi padh lunga")

async def chat(update, ctx):
    await update.message.reply_text(ask(update.effective_chat.id, update.message.text))

async def photo(update, ctx):
    await update.message.reply_chat_action("typing")
    p = update.message.photo[-1]
    f = await p.get_file()
    path = await f.download_to_drive()
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    caption = update.message.caption
    await update.message.reply_text(ask(update.effective_chat.id, caption, image_b64=b64))

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
app.add_handler(MessageHandler(filters.PHOTO, photo))

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def health():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"chamak alive")
        def log_message(self, *a):
            pass
    HTTPServer(("0.0.0.0", 7860), H).serve_forever()

threading.Thread(target=health, daemon=True).start()

app.run_polling()
