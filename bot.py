import os
import json
from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
STAFF_IDS = list(map(int, os.getenv("STAFF_IDS").split(",")))
GROUP_ID = int(os.getenv("GROUP_ID"))

# Global memory (can be replaced with file/database)
user_state = {}
user_cart = {}
order_counter = 1
staff_index = 0

# Load categories and items from JSON
with open("items.json", "r", encoding="utf-8") as f:
    categories = json.load(f)

MAIN_MENU, CATEGORY, ITEM, QUANTITY, CHECKOUT_NAME, CHECKOUT_ADDRESS, CHECKOUT_PHONE, CHECKOUT_PAYMENT, REMOVE_ITEM = range(9)

def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🍭 Shop Now"],
        ["ℹ About Us", "📞 Contact Us"]
    ], resize_keyboard=True)

def get_category_menu():
    btns = [
        list(categories.keys())[0:2],
        list(categories.keys())[2:4],
        [list(categories.keys())[4], "🛒 View Cart", "🔙 Back"]
    ]
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_items_menu(cat):
    items = list(categories[cat].keys())
    btns = [items[i:i+2] for i in range(0, len(items), 2)]
    btns.append(["🔙 Back"])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_quantity_menu(cat, item):
    options = categories[cat][item]
    btns = [[f"{qty} ₹{price}" for qty, price in options.items()]]
    btns.append(["🔙 Back"])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_cart[update.effective_chat.id] = []  # Clear cart only on /start
    await update.message.reply_text(
        "👋 Welcome to Basketo Grocery Bot!\nChoose an option below:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🍭 Shop Now":
        return await show_categories(update, context)
    elif text == "ℹ About Us":
        await update.message.reply_text("🏪 Basketo is your trusted Kerala-based grocery service!")
    elif text == "📞 Contact Us":
        await update.message.reply_text("📞 9876543210\n📍 Kerala\n🕒 8 AM to 8 PM")
    return MAIN_MENU

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose a category:", reply_markup=get_category_menu())
    return CATEGORY

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔙 Back":
        return await start(update, context)

    if text == "🛒 View Cart":
        return await handle_view_cart(update, context)

    if text == "✅ Checkout":
        return await checkout(update, context)
    
    if text == "🗑 Remove Items":
        return await remove_item_prompt(update, context)

    if text not in categories:
        await update.message.reply_text("❌ Invalid category.")
        return CATEGORY

    context.user_data["category"] = text
    await update.message.reply_text(f"Choose an item in {text}:", reply_markup=get_items_menu(text))
    return ITEM

async def handle_view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cart = user_cart.get(chat_id, [])

    if not cart:
        await update.message.reply_text("🛒 Your cart is empty.")
    else:
        msg = "🛒 Your Cart:\n"
        total = 0
        for item, qty, price in cart:
            msg += f"- {item} ({qty}) ₹{price}\n"
            total += price
        msg += f"\n*Total:* ₹{total}"
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["✅ Checkout", "🔙 Back"]], resize_keyboard=True)
        )
    return CATEGORY

async def handle_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back":
        return await show_categories(update, context)
    category = context.user_data["category"]
    if text not in categories[category]:
        await update.message.reply_text("❌ Invalid item.")
        return ITEM
    context.user_data["item"] = text
    await update.message.reply_text(
        f"Select quantity for {text}:", reply_markup=get_quantity_menu(category, text))
    return QUANTITY

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 Back":
        return await handle_item(update, context)
    if "₹" not in text:
        await update.message.reply_text("❌ Please select a valid option.")
        return QUANTITY
    item = context.user_data["item"]
    category = context.user_data["category"]
    quantity, price = text.split(" ₹")
    price = int(price)
    user_cart[update.effective_chat.id].append((item, quantity, price))
    await update.message.reply_text(f"✅ {item} ({quantity}) added to cart.", reply_markup=get_category_menu())
    return CATEGORY
async def remove_item_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cart = user_cart.get(chat_id, [])
    
    if not cart:
        await update.message.reply_text("🛒 Your cart is empty.")
        return CATEGORY

    buttons = [[f"{item} ({qty}) ₹{price}"] for item, qty, price in cart]
    buttons.append(["🔙 Cancel"])
    await update.message.reply_text("Select an item to remove:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return REMOVE_ITEM

async def handle_remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if text == "🔙 Cancel":
        return await handle_view_cart(update, context)

    cart = user_cart.get(chat_id, [])
    for i, (item, qty, price) in enumerate(cart):
        if text.startswith(f"{item} ({qty}) ₹{price}"):
            del cart[i]
            user_cart[chat_id] = cart
            await update.message.reply_text(f"❌ Removed {item} ({qty}) from your cart.")
            break
    else:
        await update.message.reply_text("❌ Item not found in cart.")
    
    return await handle_view_cart(update, context)

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Please enter your name:", reply_markup=ReplyKeyboardRemove())
    return CHECKOUT_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🏠 Enter your delivery address:")
    return CHECKOUT_ADDRESS

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text("📞 Enter your phone number:")
    return CHECKOUT_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("💰 Select payment method:",
        reply_markup=ReplyKeyboardMarkup([["Paid", "COD"]], resize_keyboard=True))
    return CHECKOUT_PAYMENT

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global order_counter, staff_index
    payment = update.message.text
    name = context.user_data["name"]
    address = context.user_data["address"]
    phone = context.user_data["phone"]
    items = user_cart[update.effective_chat.id]
    order_id = f"ORD-{order_counter:04d}"
    order_counter += 1

    total = sum(price for _, _, price in items)
    summary = f"🧾 Order ID: {order_id}\n👤 {name}\n📞 {phone}\n📍 {address}\n💰 Payment: {payment}\n\n🛒 Items:\n"
    for item, qty, price in items:
        summary += f"- {item} ({qty}) ₹{price}\n"
    summary += f"\n*Total:* ₹{total}"

    # Assign to staff
    assigned_staff = STAFF_IDS[staff_index % len(STAFF_IDS)]
    staff_index += 1

    await context.bot.send_message(chat_id=assigned_staff, text=f"📦 New Order Assigned!\n{summary}", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Order Received and Assigned to Staff ID {assigned_staff}\n{summary}", parse_mode="Markdown")
    await context.bot.send_message(chat_id=GROUP_ID, text=f"📢 New Order:\n{summary}\n👤 Assigned Staff ID: {assigned_staff}", parse_mode="Markdown")

    await update.message.reply_text("🎉 Your order has been placed! You'll receive a call soon.", reply_markup=get_main_menu())
    user_cart[update.effective_chat.id] = []
    return MAIN_MENU

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
            ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_item)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
            CHECKOUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CHECKOUT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            CHECKOUT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CHECKOUT_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_payment)],
            REMOVE_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_item)],
        },
        fallbacks=[CommandHandler("checkout", checkout)]
    )

    app.add_handler(conv)
    print("\u2705 Basketo Bot is running...")
    app.run_polling()
