#!bot_venv/bin/python3
import os, subprocess, locale, telebot, asyncio, shelve, re, logging, copy
import statistic

from telebot.async_telebot import AsyncTeleBot
from telebot import types, util
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from dotenv import load_dotenv

# for pythonanywhere.com hosting
# from telebot import asyncio_helper
# asyncio_helper.proxy = 'http://proxy.server:3128'


load_dotenv()
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
MSK = ZoneInfo("Europe/Moscow")

logger = telebot.logger
telebot.logger.setLevel(logging.ERROR)

bot = AsyncTeleBot(TELEGRAM_TOKEN)
db = shelve.open(os.path.join('db', 'storage'))


class MyUser:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.size = 5
        self.words = {}  # {'dir': [[...], [...], ...]}

        self.dir = None  # from lang -> to lang
        self.boot = None  # active trace
        self.collection = None  # quiz collection
        self.poll = None  # [question, answer]
        self.last_poll = None
        self.stat = {}  # {datetime: [corrects, wrongs], ...}
        self.dir_next_poll = []  # [dir_next_poll, ...]

    def save(self):
        db['%d' % self.user_id] = self


def get_user_from_db(message):
    u = db['%d' % message.chat.id]
    logger.info(u.__dict__)
    return u


def check_boot(m, command):
    u = get_user_from_db(m)
    return u.boot == command


@bot.message_handler(commands=['start'])
async def send_welcome(message):
    # update menu button
    await bot.delete_my_commands(scope=types.BotCommandScope(user_id=message.chat.id), language_code=None)
    await bot.set_my_commands(
        commands=[types.BotCommand("/start", "restart bot"),
                  types.BotCommand("/help", "show all commands"),
                  types.BotCommand("/options", "choose option"),
                  types.BotCommand('/run', 'run to poll'),
                  types.BotCommand('/today', 'stat for today'),
                  types.BotCommand('/month', 'stat for month'),
                  types.BotCommand('/resize', 'change count questions'),
                  ],
        scope=types.BotCommandScope(user_id=message.chat.id), )

    user_id = message.chat.id
    name = message.from_user.first_name

    if str(user_id) in db:
        msg = f'Hello, {name}. I know you. Click /help that start polling or add/del/show words'
    else:
        u = MyUser(user_id, name)
        # save user in DB
        u.save()

        msg = f'Hello, {name}. I don\'t know you. I add you in database. ' \
              f'Click /help that start polling or add/del/show words. Good luck).'

    await bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['help'])
async def send_help_information(message):
    u = get_user_from_db(message)
    commands = [(c.command, c.description)
                for c in
                await bot.get_my_commands(scope=types.BotCommandScope(user_id=message.chat.id), language_code=None)]
    msg = '\n'.join('👉 /%s: %s' % (c, d) for c, d in commands)
    if u.words:
        msg += '\nAt the moment you have selected:\n'
    for m in u.words:
        msg += '📌 "%s"\n' % m

    await bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['options', ])
async def handler_mode(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    calkback_btns = [types.InlineKeyboardButton('✏ %s' % i, callback_data=i)
                     for i in ('show_dirs', 'add_dirs', 'del_dirs', 'show_words', 'add_words', 'del_words',)]
    markup.add(*calkback_btns)
    msg = 'choose the option'
    await bot.send_message(message.chat.id, msg, reply_markup=markup)


@bot.message_handler(commands=['run', ])
async def handler_run_polling(message):
    u = get_user_from_db(message)
    u.boot = 'run'
    u.save()

    msg = 'Choose dir'
    markup = types.InlineKeyboardMarkup()
    callback_btns = [types.InlineKeyboardButton('📂 %s' % d, callback_data='CHOOSE DIR %s' % d) for d in u.words]
    callback_btns.append(types.InlineKeyboardButton('➕ 📂', callback_data='ADD DIR'))

    markup.add(*callback_btns)

    await bot.send_message(message.chat.id, msg, reply_markup=markup)


@bot.message_handler(commands=['stop', ], func=lambda message: check_boot(message, 'run'))
async def handler_stop(message):
    u = get_user_from_db(message)
    u.stop = 0
    u.boot = None
    u.collection = None
    u.poll = None
    u.last_poll = None
    u.save()
    await bot.send_message(message.chat.id, 'You stop polling.')


@bot.message_handler(commands=['resize', ])
async def hadler_resize_poll(message):
    markup = types.InlineKeyboardMarkup()
    callbakc_btns = [types.InlineKeyboardButton('%d' % i, callback_data='RESIZE %d' % i) for i in (5, 10, 15)]
    markup.add(*callbakc_btns)
    u = get_user_from_db(message)
    u.boot = 'resize'
    u.save()
    msg = f'Click size poll. Now, your size words in polling is {u.size}'
    await bot.send_message(message.chat.id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'del_dirs')
async def hadler_del_dirs(call):
    u = get_user_from_db(call.message)
    if u.words:
        msg = 'Choose dir for delete'
        markup = types.InlineKeyboardMarkup(row_width=3)
        callbakc_btns = [types.InlineKeyboardButton('➖ 📂 %s' % d, callback_data='DELETE DIR %s' % d) for d in u.words]
        markup.add(*callbakc_btns)
        await bot.send_message(call.message.chat.id, msg, reply_markup=markup)

        u.boot = 'del_dirs'
        u.save()
    else:
        msg = 'Nothing delete. Yoy have not dirs'
        await bot.send_message(call.message.chat.id, msg)


@bot.callback_query_handler(func=lambda call: re.match(r'DELETE DIR .+', call.data) and check_boot(call.message, 'del_dirs'))
async def handler_del_specific_dirs(call):
    d = call.data.removeprefix('DELETE DIR ')
    msg = f'You dir 📂 "{d}" was deleted'

    await bot.send_message(call.message.chat.id, msg)

    u = get_user_from_db(call.message)
    u.words.pop(d)
    u.boot = None
    u.save()


@bot.callback_query_handler(func=lambda call: call.data == 'show_dirs')
async def handler_show_all_dirs(call):
    u = get_user_from_db(call.message)
    msg = ''
    if u.words:
        for d in u.words:
            if u.words[d]:
                length = len(u.words[d])
                msg += f'📂 {d} has {length} words\n'
            else:
                msg += f'📂 {d} is empty.\n'

    else:
        msg = 'You have\'t dirs.'
    await bot.send_message(call.message.chat.id, msg)


@bot.callback_query_handler(func=lambda call: call.data == 'ADD DIR' or call.data == 'add_dirs')
async def handler_add_new_dir(call):
    msg = 'Enter name for new dir.'
    await bot.send_message(call.message.chat.id, msg, reply_markup=types.ForceReply())

    u = get_user_from_db(call.message)
    u.boot = 'add_dirs'
    u.save()


@bot.callback_query_handler(func=lambda call: call.data in ('add_words', 'del_words', 'show_words', 'run'))
async def handler_callback_choose_words(call):
    u = get_user_from_db(call.message)
    u.boot = call.data
    u.save()

    msg = 'Choose dir'
    markup = types.InlineKeyboardMarkup()
    callback_btns = [types.InlineKeyboardButton('📂 %s' % d, callback_data='CHOOSE DIR %s' % d) for d in u.words]
    callback_btns.append(types.InlineKeyboardButton('➕ 📂', callback_data='ADD DIR'))

    markup.add(*callback_btns)

    await bot.send_message(call.message.chat.id, msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: re.match(r'^CHOOSE DIR .+', call.data)
                                              and get_user_from_db(call.message).boot in (
                                                      'show_words', 'add_words', 'del_words', 'run'))
async def callback_query_handler_mode(call):
    u = get_user_from_db(call.message)
    u.dir = call.data.removeprefix('CHOOSE DIR ')
    u.save()

    await bot.answer_callback_query(call.id, 'You choose dir 📂 "%s".' % u.dir)

    match u.boot:
        case 'show_words':
            msg = ''
            if u.words:
                if u.words[u.dir]:
                    msg += f'📂 {u.dir}\n'
                    for q, a in u.words[u.dir]:
                        msg += '📌 %s %s\n' % (q, a)
                else:
                    msg += f'📂 {u.dir} is empty\n'
            else:
                msg = 'You collection all words is empty'
            await bot.send_message(call.message.chat.id, msg)
            u.boot = None
            u.dir = None
            u.save()

        case 'add_words':
            msg = 'Write the words for example - [quetion == answer]: бежать == run; пить == drink; and etc...'
            await bot.reply_to(call.message, msg, reply_markup=types.ForceReply())

        case 'del_words':
            if u.words[u.dir]:
                user_words = ''
                count = 0
                for q, a in u.words[u.dir]:
                    count += 1
                    user_words += '\n%d) %s == %s' % (count, q, a)
                msg = 'Write the number of words to be deleted. For example: [1 2 3 ...] and etc...'
                msg += user_words
                await bot.send_message(call.message.chat.id, msg, reply_markup=types.ForceReply())

            else:
                msg = 'Empty dir.'
                await bot.send_message(call.message.chat.id, msg)

        case 'run':
            msg = 'Start polling.\nIf you want stop polling, click or write /stop\n'

            # deepcopy
            u.collection = copy.deepcopy(u.words[u.dir])

            if u.collection:
                u.poll = u.collection.pop()
                u.save()

                poll = f'Question: <b>{u.poll[0]}</b>\nAnswer: <tg-spoiler>{u.poll[1]}</tg-spoiler>'

                msg += poll
                await bot.send_message(call.message.chat.id, msg, parse_mode='HTML', reply_markup=types.ForceReply())


            else:
                msg = f'You have not words.\nAdd new words in dir "{u.dir}"\n'
                await bot.reply_to(call.message, msg)
                u.boot = None
                u.poll = None
                u.save()

        case _:
            await bot.send_message(call.message.chat.id, 'BUG!')


@bot.callback_query_handler(func=lambda call: re.match(r'^RESIZE .+', call.data) and check_boot(call.message, 'resize'))
async def hadler_answer_resize_poll(call):
    u = get_user_from_db(call.message)
    u.size = int(call.data.removeprefix('RESIZE '))
    u.boot = None
    u.save()
    msg = f'You change size poll: {u.size}'
    await bot.send_message(call.message.chat.id, msg)


@bot.message_handler(func=lambda message: check_boot(message, 'add_dirs'))
async def adding_modes_handler(message):
    u = get_user_from_db(message)
    new_dir = message.text
    if new_dir not in u.words:
        u.words[message.text] = []
        msg = f'Ok. I added you new dir 📂 {message.text}'
    else:
        msg = 'This dir is exist'
    u.boot = None
    u.save()

    await bot.send_message(message.chat.id, msg)


@bot.message_handler(func=lambda message: check_boot(message, 'add_words'))
async def handler_add_words(message):
    u = get_user_from_db(message)
    resp_text = message.text
    if re.search(r'.+ == .+', resp_text):
        msg = ''
        temp = copy.deepcopy(u.words[u.dir])
        for line in resp_text.split(';'):
            if not line.strip():
                continue
            try:
                q, a = [i.strip() for i in line.split('==') if i.strip()]
            except ValueError as val_err:
                msg = f'Not correct format - "{resp_text}". Correct format: [quetion == answer] бежать == run; пить == drink;\n'
                await bot.send_message(message.chat.id, msg)
                u.boot = None
                u.save()

                return
            # write change words
            if [q, a] not in temp:
                temp.append([q, a])
                msg += '✅ Added: %s == %s\n' % (q, a)
            else:
                msg += '"%s == %s" is exist in dir 📂 %s\n' % (q, a, u.dir)

        await bot.send_message(message.chat.id, msg)
        # save in DB
        u.words[u.dir] = copy.deepcopy(temp)
        u.boot = None
        u.save()


    else:
        msg = f'❌ Your message not correct - "{resp_text}".' \
              f'Please, write for example: [бежать == run; пить == drink;].\n'
        await bot.send_message(message.chat.id, msg)
        u.boot = None
        u.save()


@bot.message_handler(func=lambda message: check_boot(message, 'del_words'))
async def handler_del_words(message):
    u = get_user_from_db(message)
    if all(i.isdigit() for i in message.text.split()):
        msg = ''
        # deepcopy
        new_list = copy.deepcopy(u.words[u.dir])
        for num in message.text.split():
            try:
                get_words = new_list.pop(int(num) - 1)
            except KeyError:
                msg = f'<< {num} >>. You are out of range of your words'
                await bot.send_message(message.chat.id, msg)
                return
            question, answer = get_words
            msg += '❌ Deleted %s) %s == %s\n' % (num, question, answer)

        await bot.send_message(message.chat.id, msg)
        u.words[u.dir] = new_list
    else:
        msg = 'Not correct format - "%s". Try once more. For example: [1 2 3 ...]' \
              % message.text
        await bot.send_message(message.chat.id, msg)
    u.boot = None
    u.save()


@bot.message_handler(func=lambda message: check_boot(message, 'run'))
async def handler_run(message):
    u = get_user_from_db(message)
    dt = datetime.now(MSK).date()
    if dt not in u.stat:
        u.stat[dt] = {'correct': 0, 'wrong': 0}

    if u.poll[1].lower() in map(str.lower, message.text.split()):
        msg = f'Great! Correct <u>{u.poll[1]}</u>'
        u.words[u.dir].remove(u.poll)
        u.words[u.dir].append(u.poll)

        u.stat[dt]['correct'] += 1

    else:
        msg = f'Well, wrong answer <s>{message.text}</s>\nCorrect: <u>{u.poll[1]}</u>\n'
        u.words[u.dir].remove(u.poll)
        u.words[u.dir].insert(0, u.poll)

        u.stat[dt]['wrong'] += 1

    # get feetback
    await bot.send_message(message.chat.id, msg, parse_mode='HTML')

    if u.collection:
        u.poll = u.collection.pop()
        u.save()

        msg = f'Question: <b>{u.poll[0]}</b>\nAnswer: <tg-spoiler>{u.poll[1]}</tg-spoiler>'

        await bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=types.ForceReply())

    else:

        markup = types.ReplyKeyboardMarkup(row_width=4)
        tupl = ('👽now, next 1m', '🤯again, next 10m', '😲very hard, next 4h', '🤕hard, next 1d',
                '😌good, next 2d', '🧐easy, next 4d', '🧠skip notification')
        buttons = [types.KeyboardButton(i) for i in tupl]
        markup.add(*buttons)
        msg = 'Correct answers will be listed at the end, incorrect answers at the beginning. ' \
              'Click button when you need to be notified about the next repetition of words, do not forget to complete the survey yourself'
        await bot.send_message(message.chat.id, msg, reply_markup=markup)

        u.boot = None
        u.poll = None
        u.collection = None
        u.last_poll = True
        u.save()


def create_delta(text):
    match text:
        case '👽now, next 1m':
            return timedelta(minutes=1)
        case '🤯again, next 10m':
            return timedelta(minutes=10)
        case '😲very hard, next 4h':
            return timedelta(hours=4)
        case '🤕hard, next 1d':
            return timedelta(days=1)
        case '😌good, next 2d':
            return timedelta(days=2)
        case '🧐easy, next 4d':
            return timedelta(days=4)
        case '🧠skip notification':
            return None


@bot.message_handler(func=lambda message: get_user_from_db(message).last_poll)
async def handler_last_poll(message):
    u = get_user_from_db(message)
    u.last_poll = None

    dt = datetime.now(MSK)

    if len(u.dir_next_poll) >= 100:
        u.dir_next_poll.pop(-1)

    delta = create_delta(message.text)

    if delta:
        dt += delta
        u.dir_next_poll.append(u.dir)
        fmt = dt.strftime("%d.%m.%Y in %H:%M:%S (%Z)")
        msg = f'I save you notice with 📂 {u.dir}.\nThe next notice will be ~ {fmt}. Good luck.👋'
        u.dir = None
        u.save()

        await bot.send_message(message.chat.id, msg, reply_markup=types.ReplyKeyboardRemove())

        sec = delta.days * 24 * 60 * 60 + delta.seconds
        #  waiting
        await asyncio.sleep(sec)

        d = u.dir_next_poll.pop()
        await bot.send_message(u.user_id, f'❗Hi! Don\'t forget to take the next quiz. '
                                          f'Polling should be in 📂 "{d}" dir. See you next time)')

        u.save()

    else:
        msg = 'You opted out of notification'
        u.dir = None
        u.save()
        await bot.send_message(message.chat.id, msg, reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=['today', ])
async def statistic_today_handler(message):
    u = get_user_from_db(message)
    if u.stat:
        answer = statistic.get_today_statistic(u)
        await bot.send_document(message.chat.id, answer)
    else:
        await bot.send_message(message.chat.id, 'Empty statistic.')

    subprocess.run(["rm", "example.html"])


@bot.message_handler(commands=['month', ])
async def statistic_month_handler(message):
    u = get_user_from_db(message)
    if u.stat:
        answer = statistic.get_month_statistic(u)
        await bot.send_document(message.chat.id, answer)
    else:
        await bot.send_message(message.chat.id, 'Empty statistic.')

    subprocess.run(["rm", "example.html"])


@bot.message_handler(func=lambda message: True)
async def handler_get_unknow_commands(message):
    msg = 'Sorry. I don\'t know this command'
    await bot.reply_to(message, msg)


if __name__ == '__main__':
    asyncio.run(bot.polling())
