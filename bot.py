# Write your Telegram bot here
import logging
from telegram import Update, Document, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import fitz  # PyMuPDF
import openai
import os
from fpdf import FPDF

# Настройка OpenAI API ключа
openai.api_key = 'YOUR_OPENAI_API_KEY'

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения данных сессий пользователей
user_sessions = {}

# Команда /start
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Начать анализ PDF", callback_data='start_analysis')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Привет! Выберите действие:', reply_markup=reply_markup)

# Обработка нажатия кнопок
def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'start_analysis':
        query.edit_message_text(text="Пожалуйста, отправьте мне PDF файл для анализа.")
    elif query.data == 'ask_questions':
        query.edit_message_text(text="Вы можете задать дополнительные вопросы.")

# Обработка PDF файла
def handle_document(update: Update, context: CallbackContext) -> None:
    document: Document = update.message.document
    if document.mime_type == 'application/pdf':
        file = document.get_file()
        file_path = os.path.join('/tmp', f'{document.file_id}.pdf')
        file.download(file_path)

        # Извлечение текста из PDF
        with fitz.open(file_path) as doc:
            text = ""
            for page in doc:
                text += page.get_text()

        # Анализ текста с помощью OpenAI API с использованием модели GPT-4
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты - рецензент и ридер книг, которые думает купить издательство. По каждому загруженному файлу необходимо сформировать рецензию на русском языке, которая будет содержать:

1. Заголовок: Об авторе. Содержание: Информация об авторе, если у тебя есть доступ к этой информации. 
2. Заголовок: Краткое содержание. Содержание: Краткое содержание каждой главы (отдельный абзац с названием и содержанием главы по каждому)
3. Заголовок: Основные идеи. Содержание: Саммари основных идей книги
4. Заголовок: Стиль книги. Содержание: Охарактеризуй стиль повествования. Насколько лёгкий текст для восприятия? Этот текст скорее обращён к широкой публике или академический?
5. Заголовок "Красные флаги". Содержание: Дай ответы на вопросы:
- Есть ли в тексте упоминание ЛГБТК+? В каком контексте?
- Есть ли в тексте упоминание военных операций, войн? Касается ли эта информация российско-украинского конфликта? Если нет, какие конфликты упоминаются? В каком контексте?
- Есть ли в тексте упоминание наркотиков, производства, распространения или употребления? В каком контексте?

"},
                {"role": "user", "content": "прочитай файл и напиши рецензию." }
            ]
        )
        analyzed_text = response.choices[0].message['content'].strip()

        # Сохранение проанализированного текста для последующих вопросов
        user_id = update.message.from_user.id
        user_sessions[user_id] = analyzed_text

        # Отправка результата обратно пользователю
        update.message.reply_text(analyzed_text)

        # Создание PDF с результатом
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, analyzed_text)
        pdf_output_path = os.path.join('/tmp', f'{document.file_id}_analyzed.pdf')
        pdf.output(pdf_output_path)

        # Отправка PDF пользователю
        with open(pdf_output_path, 'rb') as pdf_file:
            update.message.reply_document(pdf_file)

        # Кнопки для повторного анализа и дополнительных вопросов
        keyboard = [
            [InlineKeyboardButton("Анализировать другой PDF", callback_data='start_analysis')],
            [InlineKeyboardButton("Задать дополнительные вопросы", callback_data='ask_questions')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Выберите действие:', reply_markup=reply_markup)
    else:
        update.message.reply_text('Пожалуйста, отправьте PDF файл.')

# Обработка дополнительных вопросов
def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_sessions:
        user_question = update.message.text
        analyzed_text = user_sessions[user_id]

        # Создание запроса для OpenAI на основе анализа и вопроса
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an assistant that helps analyze PDF documents."},
                {"role": "user", "content": analyzed_text},
                {"role": "user", "content": user_question}
            ]
        )
        answer = response.choices[0].message['content'].strip()

        # Отправка ответа пользователю
        update.message.reply_text(answer)

        # Создание PDF с ответом
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, answer)
        pdf_output_path = os.path.join('/tmp', f'{user_id}_answer.pdf')
        pdf.output(pdf_output_path)

        # Отправка PDF пользователю
        with open(pdf_output_path, 'rb') as pdf_file:
            update.message.reply_document(pdf_file)
    else:
        update.message.reply_text('Пожалуйста, сначала проанализируйте PDF файл.')

def main() -> None:
    # Введите здесь токен вашего бота
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN")

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.document.mime_type("application/pdf"), handle_document))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
