""" CS1101S Attendance Bot """
# Imports
import os
import logging
from telegram.ext import Updater, CommandHandler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import redis
import time

#######################################
### SETUP REQUIRED GLOBAL VARIABLES ###
#######################################

# Function to determine column based on date
def get_week():
    cur_time = time.asctime()
    li = cur_time.split()
    month = li[1]
    date = int(li[2])  # convert to integer for comparison later
    with open('acad_calendar.json') as acad_calendar:
        data = json.load(acad_calendar)
        for date_range in data[month].keys():
            start = int(date_range.split('-')[0])
            end = int(date_range.split('-')[1])
            if start <= date <= end:
                return data[month][date_range]
    return 'Z'

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis - stores mapping of Telegram username to Row Number on Google Spreadsheet.
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
redis_pickle_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=False)
STUDENT_MAP = "STUDENT_MAP"  # Stores mapping of student's telegram @username to row num in spreadsheet
TUTOR_MAP = "TUTOR_MAP"  # Stores @usernames of tutor and state of whether they're running a session
TOKEN_MAP = "TOKEN_MAP"  # Stores the set of active tokens and their capacity at a particular instant in time

# Google Spreadsheet
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('CS1101S Bot-99365efd2073.json', scope)
gc = gspread.authorize(credentials)
wks1 = gc.open("CS1101S Reflection Attendance").sheet1
wk2 = gc.open("CS1101S Studio Attendance ").sheet1
col_name_attend = get_week()  # (TODO) resolve reference. Ask Chai.
col_name_comment = col_name_attend

##### Tutor #######
def start_session(update, context):
    # Store tutor usernames
    username = update.message.from_user.username
    print(redis_client.hexists(TUTOR_MAP, username))
    if not redis_client.hexists(TUTOR_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Insufficient number of arguments. Please enter number of students along with "
                                      "the /start_session command")
        return
    if int(context.args[0]) <= 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Number of students must be greater than 0.")
        return
    if redis_client.hget(TUTOR_MAP, username) != "No":
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="A session is already running. Please use /stop_session to stop it")
    else:
        token = generate_hash()
        redis_client.hset(TUTOR_MAP, username, token)  # Make tutor active. Store string value of token as value
        redis_client.hset(TOKEN_MAP, token, int(context.args[0]))  # Activate Token and store capacity.
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text=f'Your token is {token}. Please write it on a board to share it with students')


def stop_session(update, context):
    username = update.message.from_user.username
    if not redis_client.hexists(TUTOR_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    if not (redis_client.hget(TUTOR_MAP, username) == "Yes"):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="You've not started a session yet. Please send /start_session to start a session")
        return
    # stop the session
    token = redis_client.hget(TUTOR_MAP, username)
    redis_client.hset(TOKEN_MAP, token, 0)  # Set capacity to 0 directly. # (TODO) delete the token.
    redis_client.hset(TUTOR_MAP, username, "No")  # Tutor is not active anymore
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Session has successfully stopped. Thanks!")


def generate_hash():
    token = hash(time.time()) % 100000000
    return token


def get_week():
    # return a single capital character that is the column name
    curr_time = time.getasctime()
    li = list(curr_time)
    month = li[1]
    date = int(li[2])  # convert to integer for comparison later
    if month == "Aug":
        if date >= 12 and date <= 18:
            return 'B'  # W1
        elif date >= 19 and date < 25:
            return 'C'  # W2
        elif date >= 26:
            return 'D'  # W3
    if month == "Sept":  # (TODO) confirm if Sept or Sep shortform.
        if date <= 1:
            return 'D'  # continue from last month so W3
        elif date >= 2 and date <= 8:
            return 'E'  # W4
        elif date >= 9 and date <= 15:
            return 'F'  # W5
        elif date >= 16 and date <= 20:
            return 'G'  # W6
        elif date >= 21 and date <= 29:
            return 'R'  # Recess Week so 'R' - special week.
        elif date >= 30:
            return 'H'  # W7
    if month == "Oct":
        if date <= 6:
            return 'H'  # W7 continue from last month
        if date >= 7 and date <= 13:
            return 'I'  # W8
        if date >= 14 and date <= 20:
            return 'J'  # W 9
        if date >= 21 and date <= 27:
            return 'K'  # W 10
        if date >= 28:
            return 'L'  # W11
    if month == "Nov":
        if date <= 3:
            return 'L'  # W11
        if date >= 4 and date <= 10:
            return 'M'  # W12
        if date >= 11 and date <= 17:
            return 'N'  # W 13
    else:
        return 'Z'  # any other scenario


##### Student ##########
def start(update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Welcome to CS1101S Cadet! This bot records your attendance for reflection sessions."
                                  "Please send /setup <matric number> to get started.")


def setup(update, context):
    # check if no args
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Please enter your matric number along with the '
                                                                      'command. Eg if your matric number is '
                                                                      '123456789, enter /setup 123456789')
        return
    # check if already registered
    username = update.message.from_user.username
    if redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You're already signed up! Please wait for your"
                                                                      " tutor to give you a token to mark "
                                                                      "attendance")
        return
    # check if student can register for this module!
    matric_no = context.args[0]
    try:
        cell = wks.find(matric_no)
        row_num = cell.row
        redis_client.hset(STUDENT_MAP, username, row_num)
        context.bot.send_message(chat_id=update.message.chat_id, text="You're successfully registered! Please wait "
                                                                      "for your tutor to give you an attendance token")
        # store in redis client
    except gspread.exceptions.CellNotFound:
        context.bot.send_message(chat_id=update.message.chat_id, text="Sorry! Your matric number is not registered "
                                                                      "for this moodule. Please contact a staff "
                                                                      "member.")


def attend(update, context):
    # check if no args
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Insufficient number of arguments. Please enter '
                                                                      'the token along with the /attend command')
        return
    # check if registered or not
    username = update.message.from_user.username
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<Matric Number> to register")
        return
    # check if already attended for current week
    row_name = redis_client.hget(STUDENT_MAP, username)
    val = wks.acell(f'{col_name}{row_name}').value
    if val == 1:
        context.bot.send_message(chat_id=update.message.chat_id, text="Your attendance for this week has already been"
                                                                      "marked. Thanks!")
    else:
        # Token Logic
        token = context.args[0]
        if not redis_client.hexists(TOKEN_MAP, token):
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Token doesn't exist or has expired. Please contact your tutor.")
            return
        curr_capacity = int(redis_client.hget(TOKEN_MAP, token))
        if curr_capacity == 0:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Cannot take attendance. Your class is full. Please contact tutor as "
                                          "someone may be trying to get undue points for attendance")
            return
        else:
            # set attendance
            wks.update_acell(f'{col_name}{row_name}', '1')
            context.bot.send_message(chat_id=update.message.chat_id, text="Your attendance for this week has been "
                                                                          "successfully marked. Thanks!")
            redis_client.hset(TOKEN_MAP, token, curr_capacity - 1)  # reduce capacity
            return


def change_username(update, context):
    # just extract username and update in reddis client. Ask chai: can we do is?
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Please enter your matric number along with the '
                                                                      'command. Eg if your matric number is '
                                                                      '123456789, enter /change_username 123456789')
    username = update.message.from_user.username
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<Matric Number> to register")
        return
    matric_no = context.args[0]
    cell = wks.find(matric_no)
    row_num = cell.row
    redis_client.hset(STUDENT_MAP, username, row_num)
    context.bot.send_message(chat_id=update.message.chat_id, text="You're successfully registered! Please wait "
                                                                  "for your tutor to give you an attendance token")
    return


def main():
    """Start the bot"""
    # Create an event handler, # (TODO) hide key
    updater = Updater('***REMOVED***', use_context=True)

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('setup', setup))
    dp.add_handler(CommandHandler('attend', attend))
    dp.add_handler(CommandHandler('start_session', start_session))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
