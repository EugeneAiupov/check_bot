from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler
from telegram.ext import Filters
from solders.keypair import Keypair
import base58
from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from datetime import datetime,timedelta
from threading import Thread
import time

# административные функции
ADMIN_USER_ID = 717595524
FILE_URL_KEY = 'file_url'

def schedule_message_delation(bot, chat_id, message_id, delay):
    def task():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"Error deleting url message: {e}")
    thread = Thread(target=task)
    thread.start()

def set_file_url(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == ADMIN_USER_ID:
        new_url = ' '.join(context.args)
        context.bot_data[FILE_URL_KEY] =new_url
        update.message.reply_text(f"Новая ссылка на файл установлена: {new_url}")
    else:
        update.message.reply_text("У вас нет прав для этой операции ⛔")

def broadcast_message(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == ADMIN_USER_ID:
        text = ' '.join(context.args)
        for user_id in context.bot_data.get('user_ids', []):
            try:
                context.bot.send_message(chat_id=user_id, text=text)
            except Exception as e:
                print(f"❗ Ошибка отправки сообщения пользователю {user_id}: {e}")
        update.message.reply_text("Сообщение отправлено всем пользователям")
    else:
        update.message.reply_text("У вас нет прав для этой операции ⛔")
        
def count_users(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id == ADMIN_USER_ID:
        user_count = len(context.bot_data.get('user_ids', []))
        update.message.reply_text(f"Количество активных пользователей: {user_count}")
    else:
        update.message.reply_text("У вас нет прав для этой операции ⛔")

# Функция для генерации нового адреса кошелька
def generate_wallet_address() -> str:
    keypair = Keypair()
    wallet_address = keypair.pubkey()
    secret_key = bytes(keypair)
    
    return {
        'wallet_address': base58.b58encode(wallet_address.__bytes__()),
        'private_key': base58.b58encode(secret_key).decode('utf-8')
    }

def start(update: Update, context: CallbackContext) -> None:
    context.bot_data.setdefault('user_ids', set()).add(update.message.chat_id)
    
    message_text = ('Привет! Пожалуйста, отправьте мне адрес вашего кошелька!')
    keyboard = [
        [InlineKeyboardButton("Генерировать новый кошелек 💻", callback_data='generate')],
        [InlineKeyboardButton("Показать приватный ключ 👀", callback_data='show_private')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message_text, reply_markup=reply_markup)
    
def generate_wallet(update: Update, context: CallbackContext, from_menu = False) -> None:
    new_wallet_address = generate_wallet_address()
    context.user_data['private_key'] = new_wallet_address["private_key"]
    message_text = f'''Ваш новый адрес кошелька:
    {new_wallet_address["wallet_address"]}\n Ваш приватный ключ:
    {new_wallet_address["private_key"]}\n\n⚠️ Сохраните в безопасное место и 
    не делитесь этой информацией!'''
    
    keyboard = [
        [InlineKeyboardButton("Удалить->🗑️", callback_data='delete_data')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if from_menu:
        update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(message_text, reply_markup=reply_markup)
    
def show_private_key(update: Update, context: CallbackContext, from_menu = False) -> None:
    private_key = context.user_data.get('private_key')
    if private_key:
        message_text = f"Ваш приватный ключ: {private_key}"
        keyboard = [
            [InlineKeyboardButton("Скрыть 🔒", callback_data='hide_private_key')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        message_text = "❗ Приватный ключ не найден или уже удален."
        reply_markup = None
    
    
    
    if from_menu:
        update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(message_text, reply_markup=reply_markup)
    
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'delete_data':
        query.edit_message_text("Данные удалены ✅")
    elif query.data == 'generate':
        generate_wallet(update, context, from_menu = True)
    elif query.data == 'show_private':
        show_private_key(update, context, from_menu = True)
    elif query.data == 'hide_private_key':
        message_text = "Приватный ключ скрыт🔒"
        query.edit_message_text(message_text)
    
def check_wallet(update: Update, context: CallbackContext) -> None:
    wallet_address = update.message.text
    now = datetime.now()
    
    # Проверка времени последней успешной проверки
    last_check_time = context.user_data.get('last_check_time')
    if last_check_time and now - last_check_time < timedelta(hours=24):
        update.message.reply_text("Вы можете проверить кошелек только 1 раз в день ✌🏻")
        return
    
    # test block
    client = Client("https://solana-mainnet.g.alchemy.com/v2/A5ymEme5LgfYGrjFG4hhJTPbu6uDo_Tv")
    
    try:
        pubkey = Pubkey.from_string(wallet_address)
    except ValueError:
        update.message.reply_text("❗ Неверный формат адреса кошелька")
        return
    balance = client.get_balance(pubkey)
    balance_result = balance.value / 10**9
    message_text = f"Баланс SOL: {balance_result}\n"
    try:
        token_account_opts = TokenAccountOpts(program_id=Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'))
        token_accounts = client.get_token_accounts_by_owner_json_parsed(pubkey, token_account_opts)
        if token_accounts.value:
            for token_account in token_accounts.value:
                account_data = token_account.account
                parsed_data = account_data.data.parsed
                info = parsed_data['info']
                token_balance = info['tokenAmount']['uiAmount']
                token_mint = info['mint']
                message_text += f"\nТокен: {token_mint}, Баланс: {token_balance}"
        else:
            message_text += "❗ Нет SPL Token"
    except Exception as e:
        print(f'Error SPL token component: {e}')
        message_text += "Упс...Попробуйте другой кошелек!"
        
    update.message.reply_text(message_text) 
    # end of test block
    
    if is_wallet_valid(wallet_address):
        file_url = context.bot_data.get(FILE_URL_KEY, "Ссылка на файл не установлена")
        sent_message = update.message.reply_text(f'💥✔️ Ваш кошелек проверен. Вот ваша ссылка на скачивание файла: {file_url}')
        context.user_data['last_check_time'] = now
        schedule_message_delation(context.bot, sent_message.chat_id, sent_message.message_id, 12 * 60 * 60)
    else:
        update.message.reply_text('❗ Кошелек не найден или у него нет нужных токенов.')
        
def is_wallet_valid(wallet_address: str) -> bool:
    client = Client("https://solana-mainnet.g.alchemy.com/v2/A5ymEme5LgfYGrjFG4hhJTPbu6uDo_Tv")
    try:
        pubkey = Pubkey.from_string(wallet_address)
    except ValueError:
        print(f"Ошибка адреса")
        return False
    try:
        token_account_opts = TokenAccountOpts(program_id=Pubkey.from_string('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'))
        token_accounts = client.get_token_accounts_by_owner_json_parsed(pubkey, token_account_opts)
        if token_accounts.value:
            for token_account in token_accounts.value:
                account_data = token_account.account
                parsed_data = account_data.data.parsed
                info = parsed_data['info']
                token_balance = info['tokenAmount']['uiAmount']
                token_mint = info['mint']
                if token_balance > 0 and token_mint == 'H2iVuUsQ4dSRUUyUffh1G1fwkJu2QePRdLwzh9QzxFVT':
                    return True
            
            return False
        else:
            return False
    except Exception as e:
        print(f"Ошибка получения баланса: {e}")
        return False
    

def main():
    updater = Updater("6753885051:AAGPO_alZNmXIjYj4nlWfpfrM_zhEINXKiI", use_context=True) 
    
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("generate", generate_wallet))
    dp.add_handler(CommandHandler("show_key", show_private_key))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, check_wallet))
    dp.add_handler(CallbackQueryHandler(button))
    # Админ команды
    dp.add_handler(CommandHandler("broadcast", broadcast_message, pass_args=True))
    dp.add_handler(CommandHandler("count_users", count_users))
    dp.add_handler(CommandHandler("set_file", set_file_url, pass_args=True))
    
    updater.start_polling()
    updater.idle()
    
if __name__ == '__main__':
    main()
