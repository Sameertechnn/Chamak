import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN=os.env...ip()["BOT_TOKEN"]
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"])

PERSONA = (
    "You are Chamak, a chill desi bro AI friend. Reply in Hinglish, lowercase, short "
    "(2-4 sentences max). Funny, warm, a little roast-y but never mean. No emoji spam, "
    "max one emoji. You help with anything: studies, money, life."
)
history = {}

def ask(chat_id, text):
    msgs = history.setdefault(chat_id, [{"role": "system", "content": PERSONA}])
    msgs.append({"role": "user", "content": text})
    msgs[:] = msgs[-21:]
    r = client.chat.completions.create(model="openai/gpt-oss-20b", messages=msgs, max_tokens=300)
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
