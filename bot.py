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

MAIN_MENU, CATEGORY, ITEM, QUANTITY, CHECKOUT_NAME, CHECKOUT_ADDRESS, CHECKOUT_PHONE, CHECKOUT_PAYMENT, REMOVE_ITEM, SEARCH = range(10)

def get_main_menu():
    return ReplyKeyboardMarkup([
        ["🍭 Shop Now", "🔍 Search"],
        ["ℹ About Us", "📞 Contact Us"]
    ], resize_keyboard=True)

def get_category_menu():
    btns = [
        list(categories.keys())[0:2],
        list(categories.keys())[2:4],
        list(categories.keys())[4:6],
        list(categories.keys())[6:8],
    ]
    
    # Add last row with Cart, Search, and Back
    btns.append(["🛒 View Cart", "🔍 Search"])
    btns.append(["🔙 Back"])
    
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_items_menu(cat):
    items = list(categories[cat].keys())
    btns = [items[i:i+2] for i in range(0, len(items), 2)]
    btns.append(["🔙 Back"])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def get_quantity_menu(cat, item):
    options = categories[cat][item]
    btns = [[f"{qty} ₹{price}"] for qty, price in options.items()]
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
    elif text == "🔍 Search":
     await update.message.reply_text("🔎 Enter item name to search:")
     return SEARCH
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

    if text == "🔍 Search":
        await update.message.reply_text("🔎 Enter item name to search:")
        return SEARCH
    
    if text == "➕ Add More Items":
     return await show_categories(update, context)

    if text not in categories:
        await update.message.reply_text("❌ Invalid category.")
        return CATEGORY

    context.user_data["category"] = text
    await update.message.reply_text(
        f"Choose an item in {text}:", reply_markup=get_items_menu(text)
    )
    return ITEM

async def handle_view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cart = user_cart.get(chat_id, [])

    if not cart:
        await update.message.reply_text("🛒 Your cart is empty.")
    else:
        msg = "🛒 *Your Cart:*\n"
        total = 0
        for item, qty, price in cart:
            msg += f"- {item} ({qty}) ₹{price}\n"
            total += price
        msg += f"\n*Total:* ₹{total}"

        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Checkout"],
                ["🗑 Remove Items", "➕ Add More Items"],
                ["🔙 Back"]
            ], resize_keyboard=True)
        )

    return CATEGORY

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # 🔙 Back to categories
    if text == "🔙 Back":
        return await show_categories(update, context)

    # 🔁 Retry search
    if text == "🔁 Retry":
        await update.message.reply_text("🔎 Enter item name to search:")
        return SEARCH

    query = text.lower()
    results = []

    for cat, items in categories.items():
        for item_name in items:
            if query in item_name.lower():
                results.append((cat, item_name))

    if results:
        context.user_data["search_results"] = results
        buttons = [[item] for _, item in results]
        buttons.append(["🔙 Cancel"])
        await update.message.reply_text(
            "🔍 Select an item to add to cart:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        return ITEM
    else:
        await update.message.reply_text(
            "❌ No matching items found.\n\nTry again or go back:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔁 Retry", "🔙 Back"]
            ], resize_keyboard=True)
        )
        return SEARCH

async def handle_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔙 Back" or text == "🔙 Cancel":
        return await show_categories(update, context)

    category = context.user_data.get("category")
    search_results = context.user_data.get("search_results")

    # 🔍 If user selected an item from search results
    if search_results:
        for cat, item in search_results:
            if item == text:
                context.user_data["category"] = cat
                context.user_data["item"] = item
                context.user_data["search_results"] = None  # Clear after use
                await update.message.reply_text(
                    f"Select quantity for {item}:",
                    reply_markup=get_quantity_menu(cat, item)
                )
                return QUANTITY

    # 🛒 If user is browsing through categories
    if not category or text not in categories[category]:
        await update.message.reply_text("❌ Invalid item.")
        return ITEM

    context.user_data["item"] = text
    await update.message.reply_text(
        f"Select quantity for {text}:",
        reply_markup=get_quantity_menu(category, text)
    )
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

    # Ask for location (optional)
    await update.message.reply_text(
        "📍 If possible, please *share your exact location* using the button below:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Share Location", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        ),
        parse_mode="Markdown"
    )
    return CHECKOUT_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        context.user_data["location"] = update.message.location

        # Ask for phone next
        await update.message.reply_text(
            "📞 Now please share your phone number by tapping the button below:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Share Contact", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return CHECKOUT_PHONE

    elif update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number

        # Ask for payment method
        await update.message.reply_text(
            "💰 Select payment method:",
            reply_markup=ReplyKeyboardMarkup([["PayNow", "COD"]], resize_keyboard=True)
        )
        return CHECKOUT_PAYMENT

    else:
        await update.message.reply_text(
            "⚠️ Please *tap the button* to share your contact number.",
            parse_mode="Markdown"
        )
        return CHECKOUT_PHONE

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global order_counter, staff_index
    payment = update.message.text

    if payment == "PayNow":
        await update.message.reply_text(
            "❌ We're not accepting online payments right now.\n\nPlease choose *COD* to continue.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["COD"]], resize_keyboard=True)
        )
        return CHECKOUT_PAYMENT

    # Retrieve user details
    name = context.user_data["name"]
    address = context.user_data["address"]
    phone = context.user_data.get("phone", "Not provided")
    location = context.user_data.get("location")
    items = user_cart[update.effective_chat.id]
    order_id = f"ORD-{order_counter:04d}"
    order_counter += 1

    total = sum(price for _, _, price in items)

    # Build order summary
    summary = f"🧾 *Order ID:* `{order_id}`\n"
    summary += f"👤 *Name:* {name}\n"
    summary += f"📞 [{phone}](tel:{phone})\n"
    summary += f"📍 *Address:* {address}\n"
    if location:
        lat = location.latitude
        lon = location.longitude
        maps_url = f"https://maps.google.com/?q={lat},{lon}"
        summary += f"📌 *Location:* [View on Map]({maps_url})\n"
    summary += f"💰 *Payment:* {payment}\n\n🛒 *Items:*\n"

    for item, qty, price in items:
        summary += f"- {item} ({qty}) ₹{price}\n"
    summary += f"\n*Total:* ₹{total}"

    # Assign to staff
    assigned_staff = STAFF_IDS[staff_index % len(STAFF_IDS)]
    staff_index += 1

    # Send order summary
    for chat_id in [assigned_staff, ADMIN_ID, GROUP_ID]:
        await context.bot.send_message(chat_id=chat_id, text=summary, parse_mode="Markdown")

    # Confirm to user
    await update.message.reply_text(
        "🎉 Your order has been placed! You'll receive a call soon.",
        reply_markup=get_main_menu()
    )

    # Clear cart
    user_cart[update.effective_chat.id] = []
    return MAIN_MENU

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
        SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
        CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
        ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_item)],
        QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)],
        CHECKOUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        CHECKOUT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
        CHECKOUT_PHONE: [
    MessageHandler(filters.CONTACT, get_phone),
    MessageHandler(filters.LOCATION, get_phone),
    MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
],      CHECKOUT_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_payment)],
        REMOVE_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_item)],
    },
    fallbacks=[
        CommandHandler("start", start),
        CommandHandler("checkout", checkout)
    ]
)
    app.add_handler(conv)
    print("✅ Basketo Bot is running...")
    app.run_polling()
    