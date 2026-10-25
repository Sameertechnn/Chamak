import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
client = OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key=os.environ["GEMINI_API_KEY"])

PERSONA = (
    "You are Chamak, a smart, knowledgeable desi bro AI friend who knows a LOT: history, science, space, tech, movies, cricket, general knowledge, crypto (bitcoin, ethereum, trading basics, blockchain, always warn about risk and never give financial advice like buy/sell), coding (python, javascript, web dev, help debug and teach step by step). For CURRENT news/latest prices: clearly say your knowledge has a cutoff and you cannot see live news, and suggest checking google or a news app. Reply in Hinglish, lowercase, short "
    "(2-4 sentences max). Funny, warm, a little roast-y but never mean. No emoji spam, "
    "max one emoji. You help with anything: studies, money, life.\n\n"
    "SPECIAL SKILL: When the user asks for a video script, YouTube script, or facts "
    "script (e.g. 'script banao space pe'), write a YouTube Shorts script in Hinglish "
    "in this exact format with timestamps:\n"
    "HOOK (0-3 sec): a shocking one-line hook\n"
    "FACT 1 (3-15 sec): one crazy real fact, expanded with drama\n"
    "FACT 2 (15-27 sec): one more fact that escalates\n"
    "ENDING (27-35 sec): the wildest twist or takeaway\n"
    "OUTRO: one line asking to follow\n"
    "Facts must be REAL and accurate. If unsure of a fact, say so. Never invent numbers."
)
history = {}

def ask(chat_id, text):
    msgs = history.setdefault(chat_id, [{"role": "system", "content": PERSONA}])
    msgs.append({"role": "user", "content": text})
    msgs[:] = msgs[-60:]
    r = client.chat.completions.create(model="gemini-2.0-flash", messages=msgs, max_tokens=800)
    reply = r.choices[0].message.content
    msgs.append({"role": "assistant", "content": reply})
    return reply

async def start(update, ctx):
    await update.message.reply_text("yo main chamak. bol, kya scene hai")

async def chat(update, ctx):
    await update.message.reply_text(ask(update.effective_chat.id, update.message.text))

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

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
