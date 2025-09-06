import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import logging
import urllib.parse
import os
from utils_zoo import AnimalQuiz
import random
import time
from dotenv import load_dotenv
from telebot import apihelper

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')

logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TotemAnimalBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.user_data = {}
        self.quiz = AnimalQuiz()
        self.setup_handlers()

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self.user_data[message.chat.id] = {'answers': [], 'scores': []}

            welcome_text = (
                "🐾 Добро пожаловать в официальный бот Московского зоопарка! 🐾\n\n"
                "Я помогу вам:\n"
                "• Определить ваше тотемное животное через увлекательную викторину\n"
                "• Узнать о программе опекунства над животными\n"
                "• Связаться с сотрудниками зоопарка\n"
                "• Оставить отзыв о вашем опыте\n\n"
                "Выберите действие из меню ниже или используйте команды:\n"
                "/start - Главное меню\n"
                "/help - Справка по командам\n"
                "/quiz - Начать викторину\n"
                "/guardianship - Информация об опекунстве\n"
                "/contact - Контакты зоопарка\n"
                "/feedback - Оставить отзыв\n\n"
                "Начните с викторины, чтобы узнать ваше тотемное животное! 🦁"
            )

            self.bot.send_message(message.chat.id, welcome_text)
            self.user_data[message.chat.id] = {'answers': [], 'scores': []}
            self.send_main_menu(message.chat.id)

        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            self.send_help(message.chat.id)

        @self.bot.message_handler(commands=['feedback'])
        def feedback_command(message):
            self.collect_feedback(message.chat.id)

        @self.bot.message_handler(commands=['guardianship'])
        def guardianship_command(message):
            self.send_guardianship_info(message.chat.id)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_query(call):
            try:
                if call.data == 'start_quiz':
                    self.start_quiz(call.message.chat.id)
                elif call.data.startswith('q'):
                    self.process_quiz_answer(call)
                elif call.data == 'learn_more':
                    self.send_guardianship_info(call.message.chat.id)
                elif call.data == 'retry':
                    self.start_quiz(call.message.chat.id)
                elif call.data == 'send_message':
                    self.handle_send_message(call)
            except Exception as e:
                logging.error(f"Error handling callback: {e}")


        @self.bot.message_handler(commands=['contact'])
        def contact_command(message):
            self.contact_staff(message.chat.id)

        @self.bot.message_handler(func=lambda message: message.text in ["Начать викторину", "Помощь", "Контакты", "Оставить отзыв"])
        def handle_main_menu(message):
            try:
                if message.text == "Начать викторину":
                    self.start_quiz(message.chat.id)
                elif message.text == "Помощь":
                    self.send_help(message.chat.id)
                elif message.text == "Контакты":
                    self.contact_staff(message.chat.id)
                elif message.text == "Оставить отзыв":
                    self.collect_feedback(message.chat.id)
            except Exception as e:
                logging.error(f"Error handling main menu: {e}")

        @self.bot.message_handler(commands=['quiz'])
        def quiz_command(message):
            self.start_quiz(message.chat.id)

    def handle_send_message(self, call):
        self.bot.send_message(call.message.chat.id, "Введите ваше сообщение для отправки:")
        self.bot.register_next_step_handler(call.message, self.process_message)

    def process_message(self, message):
        user_message = message.text
        self.bot.send_message(message.chat.id, f"Ваше сообщение: '{user_message}' было отправлено.")
        # Сохранение отзыва в файл
        try:
           self.save_feedback(user_message, message.chat.id)

        except Exception as e:
            logging.error(f"Ошибка при сохранении отзыва: {e}")
            self.bot.send_message(message.chat.id, "Произошла ошибка при сохранении вашего сообщения.")

    def collect_feedback(self, chat_id):
        self.bot.send_message(chat_id, "Пожалуйста, оставьте ваш отзыв:")
        self.bot.register_next_step_handler_by_chat_id(chat_id, self.process_message)

    def save_feedback(self, feedback_text, user_id):
        with open('feedback.txt', 'a', encoding='utf-8') as file:
            file.write(f"Отзыв от пользователя {user_id}: {feedback_text}\n")
        logging.info("Отзыв успешно сохранен.")

    def start_quiz(self, chat_id):
        self.user_data[chat_id] = {'answers': [], 'scores': []}
        self.ask_question(chat_id, 0)

    def ask_question(self, chat_id, question_number):
        question_data = self.quiz.questions[question_number]
        markup = InlineKeyboardMarkup()
        for i, option in enumerate(question_data["options"]):
            markup.add(InlineKeyboardButton(option, callback_data=f'q{question_number}{i}'))
        self.bot.send_message(chat_id, question_data["question"], reply_markup=markup)

    def process_quiz_answer(self, call):
        question_number = int(call.data[1])
        answer_index = int(call.data[2])
        score = self.quiz.questions[question_number]["weights"][answer_index]
        self.user_data[call.message.chat.id]['answers'].append(answer_index)
        self.user_data[call.message.chat.id]['scores'].append(score)

        if question_number < len(self.quiz.questions) - 1:
            self.ask_question(call.message.chat.id, question_number + 1)
        else:
            animal_name, image_path, info = self.quiz.determine_animal(self.user_data[call.message.chat.id]['answers'])
            self.send_animal_result(call.message.chat.id, animal_name, image_path, info)
            del self.user_data[call.message.chat.id]

    def send_animal_result(self, chat_id, animal_name, image_path, info):
        guardianship_info = (
            "Вы можете стать опекуном этого животного в Московском зоопарке. "
            "Это поможет поддерживать и заботиться о вашем тотемном животном. "
            "Нажмите на кнопку ниже, чтобы узнать больше."
        )
        if image_path:
            with open(image_path, 'rb') as photo:
                self.bot.send_photo(chat_id, photo, caption=f"Ваше тотемное животное: {animal_name}\n\n{info}\n\n{guardianship_info}")
        else:
            self.bot.send_message(chat_id, f"Ваше тотемное животное: {animal_name}. Изображение недоступно.\n\n{info}\n\n{guardianship_info}")

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Попробовать ещё раз?", callback_data='retry'))
        markup.add(InlineKeyboardButton("❤️Опекунство в Московском зоопарке", callback_data='learn_more'))
        self.bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)
        self.share_results(chat_id, animal_name)

    def send_guardianship_info(self, chat_id):
        guardianship_info = (
            "❤️Опекать – значит помогать любимым животным.\n"
            "Участие в программе «Клуб друзей зоопарка» — это помощь в содержании наших обитателей, "
            "а также ваш личный вклад в дело сохранения биоразнообразия Земли и развитие нашего зоопарка.\n"
            "🥹Основная задача Московского зоопарка с самого начала его существования это — сохранение "
            "биоразнообразия планеты. Когда вы берете под опеку животное, вы помогаете нам в этом благородном "
            "деле.\n\nСтать опекуном очень просто!\n-Выберите животное, которое Вы хотели бы опекать.\n-Определите сумму "
            "пожертвования(взносы мы можем разделить).\n-Затем мы с Вами согласуем договор. Он очень простой,\nобещаем 😇\n"
            "-Готово! Ждем Вас в гости, чтобы подписать договор и передать Вам Вашу карту опекуна.\n\n✨Нажмите на кнопку ниже, чтобы узнать подробнее об опекунстве в Московском зоопарке."
        )
        markup = InlineKeyboardMarkup()
        guardianship_button = InlineKeyboardButton("Узнать больше", url="https://moscowzoo.ru/about/guardianship")
        markup.add(guardianship_button)
        self.bot.send_message(chat_id, guardianship_info, reply_markup=markup)



    def send_main_menu(self, chat_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("Начать викторину"),
                   KeyboardButton("Помощь"),
                   KeyboardButton("Контакты"),
                   KeyboardButton("Оставить отзыв"))
        self.bot.send_message(chat_id, "Добро пожаловать в главное меню. Выберите действие:", reply_markup=markup)

    def send_help(self, chat_id):
        help_text = (
            "🐾 Справка по командам бота Московского зоопарка:\n\n"
            "/start - Главное меню и приветствие\n"
            "/help - Показать эту справку\n"
            "/quiz - Начать викторину для определения тотемного животного\n"
            "/guardianship - Узнать об опекунстве животных\n"
            "/contact - Контакты зоопарка\n"
            "/feedback - Оставить отзыв о работе бота\n\n"
            "Вы также можете использовать кнопки меню для навигации!"
        )
        self.bot.send_message(chat_id, help_text)

    def contact_staff(self, chat_id):
        contact_info = (
            "Свяжитесь с нами для дополнительной информации:\n"
            "Наш сайт: https://moscowzoo.ru/\n"
            "Telegram: https://t.me/Moscowzoo_official\n"
            "YouTube канал: https://www.youtube.com/@Moscowzooofficial\n"
            "Сообщество Вконтакте: https://vk.com/moscow_zoo\n"
            "Группа в Одноклассниках: https://ok.ru/moscowzoo\n"
            "Телефон: +7 499 252 29 51\n"
            "Вы можете отправить сообщение сотруднику, нажав на кнопку ниже."
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Отправить сообщение", callback_data='send_message'))
        self.bot.send_message(chat_id, contact_info, reply_markup=markup)

    def share_results(self, chat_id, animal_name):
        share_text = f"Мое тотемное животное — {animal_name}! Узнайте своё с помощью этого бота!"
        bot_link = "https://t.me/MoscowZooQxstay_bot"

        # Кодирование текста и ссылки для URL
        encoded_link = urllib.parse.quote_plus(bot_link)
        encoded_text = urllib.parse.quote_plus(share_text)

        # Создание ссылок для различных социальных сетей
        telegram_url = f"https://t.me/share/url?url={encoded_link}&text={encoded_text}"
        vk_url = f"https://vk.com/share.php?url={encoded_link}&title={encoded_text}"
        ok_url = f"https://connect.ok.ru/offer?url={encoded_link}&title={encoded_text}"
        whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_text}%20{encoded_link}"

        # Отправка сообщения с кнопками для каждого сервиса
        options_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Поделиться в Telegram", url=telegram_url)],
        [InlineKeyboardButton("Поделиться в ВКонтакте", url=vk_url)],
        [InlineKeyboardButton("Поделиться в Одноклассниках", url=ok_url)],
        [InlineKeyboardButton("Поделиться в WhatsApp", url=whatsapp_url)]

    ])
        self.bot.send_message(chat_id, "Поделитесь результатами в социальных сетях:", reply_markup=options_markup)

    def run(self):
        try:
            logging.info("Бот запущен.")
            self.bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"Ошибка в работе бота: {e}")
            time.sleep(5)  # Задержка перед повторным запуском
            self.run()

#Удаляем вебхук
bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

if __name__ == "__main__":
    bot = TotemAnimalBot(API_TOKEN)
    bot.run()
