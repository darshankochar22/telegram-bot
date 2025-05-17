from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os
import groq
import re
from collections import defaultdict
import time
from dotenv import load_dotenv
load_dotenv()


TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
groq_client = groq.Client(api_key=os.environ.get("GROQ_API_KEY"))
GROQ_MODEL = "llama3-8b-8192" 

conversation_history = defaultdict(list)
CONVERSATION_EXPIRY = 3600 

SYSTEM_PROMPT = """You are Sigmoydbot, a helpful and conversational AI assistant. 
You have a friendly personality and maintain context through conversations.
You provide concise but thoughtful responses and can discuss a wide range of topics.
You should remember information shared by users during the conversation and give short replies talk like a person."""

def is_bot_mentioned(text, bot_username):
    pattern = f"@{re.escape(bot_username)}"
    return bool(re.search(pattern, text, re.IGNORECASE))

def update_conversation(user_id, role, content):
    conversation_history[user_id].append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })
    
    # Clean up old messages (older than CONVERSATION_EXPIRY)
    current_time = time.time()
    conversation_history[user_id] = [
        msg for msg in conversation_history[user_id] 
        if current_time - msg["timestamp"] < CONVERSATION_EXPIRY
    ]

# Get formatted conversation history for Groq API
def get_groq_messages(user_id):
    # Always start with the system message
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add conversation history (without timestamps)
    for msg in conversation_history[user_id]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    return messages

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Clear any existing conversation for this user when they start fresh
    conversation_history[user_id] = []
    
    await update.message.reply_text("Hi! I'm Sigmoydbot. Tag me with @Sigmoydbot or reply to my messages to have a conversation! I'll remember what we talk about.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get the bot's username from context
    bot_username = context.bot.username
    message_text = update.message.text
    user_id = update.effective_user.id
    
    # Check if the message is a reply to the bot's message
    is_reply_to_bot = False
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        is_reply_to_bot = update.message.reply_to_message.from_user.username == bot_username
    
    # Respond if the bot is mentioned or if the message is replying to the bot
    if is_bot_mentioned(message_text, bot_username) or is_reply_to_bot:
        # Process message with Groq
        try:
            # Extract the actual query 
            query = message_text
            if is_bot_mentioned(message_text, bot_username):
                # Remove the bot mention if it exists
                query = re.sub(f"@{re.escape(bot_username)}", "", message_text, flags=re.IGNORECASE).strip()
            
            # Update conversation with user's message
            update_conversation(user_id, "user", query)
            
            # Get conversation history for this user
            messages = get_groq_messages(user_id)
            
            # Generate a response using Groq with conversation history
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=500
            )
            
            # Extract the response
            bot_response = response.choices[0].message.content
            
            # Update conversation with bot's response
            update_conversation(user_id, "assistant", bot_response)
            
            # Send the response
            await update.message.reply_text(bot_response)
            
        except Exception as e:
            await update.message.reply_text(f"Sorry, I encountered an error: {str(e)}")
    
    # Don't respond if the bot is not mentioned or replied to

def main():
    # Set up your bot with the token
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()