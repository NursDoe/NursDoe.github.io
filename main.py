import logging
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import sqlite3
import random

def generate_derangement(lst):
    derangement = lst[:]
    while True:
        random.shuffle(derangement)
        if all(derangement[i] != lst[i] for i in range(len(lst))):
            return derangement

def format_leaderboard(leaderboard_data):
    header = "<b>№ |    Очки | Имя</b>"
    separator = "————————————————————"
    
    rows = [f"{i+1}   |    {str(row[3]).rjust(10-len(str(row[3])))} | <a href='tg://user?id={row[0]}'>{row[1]} {row[2]}</a> " for i, row in enumerate(leaderboard_data)]
    
    formatted_leaderboard = f"{header}\n{separator}\n" + "\n".join(rows)
    
    return formatted_leaderboard


token_api = '7415614137:AAEgYD2AWd2PL9dXzRO_PzyM7jitvAQlVvI'

dbPath = 'tgbotdb.sql'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    chatID = update.message.chat.id
    membersCount = await context.bot.get_chat_member_count(update.message.chat.id) - 1
    print(membersCount)
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM challengers WHERE chatID = ?', (chatID,))
    isPresent = cur.fetchone()[0]
    if not isPresent:
        await context.bot.send_message(update.message.chat.id, f'Чтобы присоединиться к игре, напишите команду /join. Игра начнется как только все участники присоединятся к игре. В настоящее время участвуют: 0/{membersCount}.')
    else:
        await context.bot.send_message(update.message.chat.id, 'Игра уже запущена. Чтобы участвовать напишите /join.')
    cur.close()
    conn.close()


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    chatID = update.message.chat.id
    userID = update.message.from_user.id

    cur.execute('SELECT COUNT(*) FROM challengers WHERE chatID = ? AND userID = ?', (chatID, userID))
    isPresent = cur.fetchone()[0]
    if not isPresent:
        cur.execute('SELECT COUNT(*) FROM challengers WHERE chatID = ?', (chatID,))
        count = cur.fetchone()[0]
        membersCount = await context.bot.get_chat_member_count(update.message.chat.id) - 1

        firstName = update.message.from_user.first_name
        lastName = update.message.from_user.last_name
        cur.execute('INSERT INTO challengers VALUES (?, ?, ?, ?, 0)', (chatID, userID, firstName, lastName if lastName is not None else ''))
        conn.commit()

        await context.bot.send_message(chatID, f'{update.message.from_user.first_name} {update.message.from_user.last_name} присоединился к игре! В настоящее время участвуют {count+1}/{membersCount}')

        if count+1 == membersCount:
            await context.bot.send_message(chatID, 'Все участники присоединились! Введите список заданий.')
    else:
        await context.bot.send_message(chatID, 'Вы уже участвуете!')
    cur.close()
    conn.close()


async def inserttasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userAddressing = await context.bot.get_chat_member(update.message.chat.id, update.message.from_user.id)
    if userAddressing.status not in ['administrator', 'creator']:
        await context.bot.send_message(update.message.chat.id, "Только администратор может пользоваться этой командой")
    else:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()
        chatID = update.message.chat.id

        cur.execute('SELECT userID FROM challengers WHERE chatID = ?', (chatID,))
        usersList = [x[0] for x in cur.fetchall()]
        membersCount = await context.bot.get_chat_member_count(chatID)
        print(membersCount)
        if len(usersList) == membersCount -1:
            taskIDs = list()
            taskRecords = list()
            splited = update.message.text[12:].strip().splitlines()
            for i in range(0, len(splited)):
                l = splited[i].strip().split(', ')
                l[0] = True if l[0]=='1' else False
                l[3] = int(l[3])
                random_number = random.randint(100000000, 999999999)
                taskIDs.append(random_number)
                taskRecords.append([chatID, random_number] + l)
            cur.executemany('INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)', taskRecords)

            specTasks = taskIDs[-len(usersList):]
            random.shuffle(specTasks)
            specTasksShaped = [specTasks, generate_derangement(specTasks)]
            completionList = list()
            for i in range(0, len(usersList)):
                for k in taskIDs[:-len(usersList)]:
                    completionList.append([chatID, k, usersList[i]])
                for n in specTasksShaped:
                    completionList.append([chatID, n[i], usersList[i]])
            cur.executemany('INSERT INTO completions VALUES (?, ?, ?, False)', completionList)
            conn.commit()
            await context.bot.send_message(chatID, f'Успех! Введите /allTasks для просмотра всех заданий.')
        else:
            await context.bot.send_message(chatID, 'Не все участники присоединились')
        cur.close()
        conn.close()


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    chatID = update.message.chat.id
    
    cur.execute('SELECT userID, firstName, lastName, points FROM challengers WHERE chatID = ? ORDER BY points DESC', (chatID,))
    tableRecords = cur.fetchall()

    formmattedTable = format_leaderboard(tableRecords)

    await context.bot.send_message(chatID, formmattedTable, parse_mode="HTML")

    cur.close()
    conn.close()
    

async def mylist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    chatID = update.message.chat.id
    userID = update.message.from_user.id
    firstName = update.message.from_user.first_name
    lastName = update.message.from_user.last_name

    cur.execute('''SELECT tasks.taskName, tasks.taskDescription, tasks.taskValue, completions.isCompleted, completions.taskID 
                FROM tasks
                INNER JOIN completions
                ON tasks.chatID = completions.chatID AND tasks.taskID = completions.taskID
                WHERE completions.chatID = ? AND completions.userID = ?
                ORDER BY tasks.taskValue DESC
                ''', (chatID, userID))
    myTasks = cur.fetchall()
    uncompleted = [f'\n <b>○ {x[0]} — {x[2]} о.</b>\n{x[1]}\nКод выполнения: <code>{x[4]}</code>\n' for x in myTasks if not x[3]]
    completed = [f'\n <b>● {x[0]} — {x[2]} о.</b>\n{x[1]}\n' for x in myTasks if x[3]]

    completedText = "\n\n<b><i>Выполнено✅</i></b>" + "".join(completed) if completed else ''

    toSend = f"<a href='tg://user?id={userID}'>{firstName} {lastName}</a>, список твоих заданий выглядит так:\n\n<b><i>Доступно🟢</i></b>" + "".join(uncompleted) + completedText

    await context.bot.send_message(chatID, toSend, parse_mode="HTML")

    cur.close()
    conn.close()


async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    receivedText = update.message.text.strip()
    if len(receivedText.split()) == 2:
        taskID = receivedText.split()[1]
        if len(taskID)==9 and taskID.isdigit():
            taskID = int(taskID)
            chatID = update.message.chat.id
            userID = update.message.from_user.id
            conn = sqlite3.connect(dbPath)
            cur = conn.cursor()

            cur.execute('SELECT COUNT(*) FROM completions WHERE userID = ? AND taskID = ? AND isCompleted = False', (userID, taskID))
            isPresent = cur.fetchone()[0]
            cur.close()
            conn.close()
            if isPresent:
                keyboard = [
                    [InlineKeyboardButton(text="Подтвердить✔️", callback_data=f"confirmButton:{userID}:{taskID}:{chatID}"), 
                     InlineKeyboardButton(text="Отмена❌", callback_data=f"cancelButton:{userID}")], 
                    ]
                markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(update.message.chat.id, "Подтвердите выполнение:", reply_markup=markup)
            else:
                await context.bot.send_message(update.message.chat.id, "Код не действителен или задание вам недоступно.")
        else:
            await context.bot.send_message(update.message.chat.id, "Код не действителен")
    else:
        await context.bot.send_message(update.message.chat.id, "Чтобы сообщить выполнение задания напишите '/complete *код выполнения*'.")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(':')
    action = data[0]
    userID = int(data[1])
    clickedUserID = query.from_user.id
    if clickedUserID == userID:
        await context.bot.edit_message_reply_markup(query.message.chat.id, query.message.message_id, reply_markup=None)
        if action == "confirmButton":
            taskID = int(data[2])
            chatID = int(data[3])
            fullName = query.from_user.first_name + ' ' + query.from_user.last_name
            await context.bot.answer_callback_query(query.id, "Обработка...")
            if action == "confirmButton":
                conn = sqlite3.connect(dbPath)
                cur = conn.cursor()
                cur.execute('SELECT taskName, taskValue FROM tasks WHERE chatID = ? AND taskID = ?', (chatID, taskID))
                taskData = cur.fetchone()
                cur.execute('UPDATE completions SET isCompleted = True WHERE userID = ? AND taskID = ? AND isCompleted = False', (userID, taskID))
                cur.execute('UPDATE challengers SET points = points + ? WHERE chatID = ? AND userID = ?', (taskData[1], chatID, userID))
                conn.commit()
                cur.close()
                conn.close()
                await context.bot.send_message(query.message.chat.id, f"<a href='tg://user?id={userID}'>{fullName}</a> выполнил задание '{taskData[0]}'. Юху, +{taskData[1]}", parse_mode="HTML")
        elif action == "cancelButton":
            await context.bot.send_message(query.message.chat.id, "Подтверждение отменено")
    else:
        await context.bot.answer_callback_query(query.id, "Не для тебя эту кнопку растили")


async def alltasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    chatID = update.message.chat.id

    cur.execute('SELECT taskName, taskDescription, taskValue FROM tasks WHERE chatID = ? AND isCommon = True ORDER BY taskValue DESC', (chatID,))
    commonTasks = cur.fetchall()
    commonTasksText = [f'\n<b>• {row[0]} — {row[2]} о.</b>\n{row[1]}\n' for row in commonTasks]

    cur.execute('''SELECT tasks.taskName, tasks.taskDescription, tasks.taskValue, challengers.firstName, challengers.lastName, challengers.userID 
                FROM tasks 
                INNER JOIN completions
                INNER JOIN challengers
                ON completions.taskID = tasks.taskID AND completions.chatID = tasks.chatID AND completions.userID = challengers.userID
                WHERE completions.chatID = ? AND tasks.isCommon = False
                ORDER BY completions.userID ASC''', (chatID,))
    specTasks = cur.fetchall()
    specTasksText = ''
    prevUsID = 0
    for row in specTasks:
        if prevUsID != row[5]:
            specTasksText += f"\n\n<a href='tg://user?id={row[5]}'><b><i>{row[3]} {row[4]}:</i></b></a>"
            prevUsID = row[5]
        specTasksText += f'\n<b>• {row[0]} — {row[2]} о.</b>\n{row[1]}\n'

    toSend = "<b><i>👥Общие задания:</i></b>" + ''.join(commonTasksText) + specTasksText

    await context.bot.send_message(chatID, toSend, parse_mode="HTML")

    cur.close()
    conn.close()


async def summit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(dbPath)
    cur = conn.cursor()
    chatID = update.message.chat.id
    cur.execute('SELECT userID, firstName, lastName FROM challengers WHERE chatID = ?', (chatID,))
    users = cur.fetchall()
    toSend = ''
    for i in users:
        toSend += f"<a href='tg://user?id={i[0]}'>{i[1]} {i[2]}</a>,  "
    await context.bot.send_message(chatID, toSend, parse_mode="HTML")


async def easywin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Хуй тебе, дурачок",
                                   reply_to_message_id=update.message.message_id)


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userAddressing = await context.bot.get_chat_member(update.message.chat.id, update.message.from_user.id)
    if userAddressing.status not in ['administrator', 'creator']:
        await context.bot.send_message(update.message.chat.id, "Только администратор может пользоваться этой командой")
    else:
        conn = sqlite3.connect(dbPath)
        cur = conn.cursor()

        cur.execute('SELECT * FROM challengers')
        res1 = cur.fetchall()
        cur.execute('SELECT * FROM tasks')
        res2 = cur.fetchall()
        cur.execute('SELECT * FROM completions')
        res3 = cur.fetchall()

        cur.close()
        conn.close()
        await context.bot.send_message(update.message.chat.id, f'Challengers:\n {res1}\n Tasks:\n {res2}\n Completions:\n {res3}\n')


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userAddressing = await context.bot.get_chat_member(update.message.chat.id, update.message.from_user.id)
    if userAddressing.status not in ['administrator', 'creator']:
        await context.bot.send_message(update.message.chat.id, "Только администратор может пользоваться этой командой")
    else:
        if 'confirm' in update.message.text.lower():
            conn = sqlite3.connect(dbPath)
            cur = conn.cursor()
            chatID = update.message.chat.id

            cur.execute('DELETE FROM challengers WHERE chatID = ?', (chatID,))
            cur.execute('DELETE FROM tasks WHERE chatID = ?', (chatID,))
            cur.execute('DELETE FROM completions WHERE chatID = ?', (chatID,))
            conn.commit()
            cur.close()
            conn.close()

            await context.bot.send_message(update.message.chat.id, 'Все данные вашей игры были очищены. Напишите /start чтобы начать новую игру.')
        else:
            await context.bot.send_message(update.message.chat.id, "Напишите 'confirm' вместе с /delete для удаления текущей игры.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otvetki = [
    'Не пиши мне, извращенец!',
    'Извини, у меня уже есть парень...',
    'Сорри, не знакомлюсь с людьми в интернете.',
    'Отвечу как только от тебя перестанет вонять.',
    'Чел, отвяжись, мне 13',
    'Опять ты! Снова хочешь купить мои колготки?',
    'Знаешь сколько таких как ты мне в день пишет?'
    ]
    await context.bot.send_message(update.effective_chat.id, otvetki[random.randint(0,len(otvetki)-1)])


if __name__ == '__main__':
    application = ApplicationBuilder().token(token_api).build()
    
    start_handler = CommandHandler('start', start, filters=filters.ChatType.GROUPS)
    join_handler = CommandHandler('join', join, filters=filters.ChatType.GROUPS)
    inserttasks_handler = CommandHandler('inserttasks', inserttasks, filters=filters.ChatType.GROUPS)
    leaderboard_handler = CommandHandler('leaderboard', leaderboard, filters=filters.ChatType.GROUPS)
    mylist_handler = CommandHandler('mylist', mylist, filters=filters.ChatType.GROUPS)
    complete_handler = CommandHandler('complete', complete, filters=filters.ChatType.GROUPS)
    alltasks_handler = CommandHandler('alltasks', alltasks, filters=filters.ChatType.GROUPS)
    summit_handler = CommandHandler('summit', summit, filters=filters.ChatType.GROUPS)
    easywin_handler = CommandHandler('easywin', easywin, filters=filters.ChatType.GROUPS)
    show_handler = CommandHandler('show', show, filters=filters.ChatType.GROUPS)
    delete_handler = CommandHandler('delete', delete, filters=filters.ChatType.GROUPS)
    unknown_handler = MessageHandler(filters.ALL, unknown)

    application.add_handler(start_handler)
    application.add_handler(join_handler)
    application.add_handler(inserttasks_handler)
    application.add_handler(leaderboard_handler)
    application.add_handler(mylist_handler)
    application.add_handler(complete_handler)
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(alltasks_handler)
    application.add_handler(summit_handler)
    application.add_handler(easywin_handler)
    application.add_handler(show_handler)
    application.add_handler(delete_handler)
    application.add_handler(unknown_handler)

    application.run_polling(poll_interval=2)