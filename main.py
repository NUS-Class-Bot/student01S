"""
This version is specifically trimmed-down for AY 2020/21 Sem 1. For the complete code, please refer to the master branch.
"""
# Imports
import os
import json
import logging
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import redis
import time

#######################################
### SETUP REQUIRED GLOBAL VARIABLES ###
#######################################

# Function to determine column based on date for Reflection Spreadsheet


def get_week_ref():
    cur_time = time.asctime()
    print(cur_time)
    li = cur_time.split()
    month = li[1]
    date = int(li[2])  # convert to integer for comparison later
    with open('acad_calendar.json') as acad_calendar:
        data = json.load(acad_calendar)
        for date_range in data[month].keys():
            start = int(date_range.split('-')[0])
            print("start" + str(start))
            end = int(date_range.split('-')[1])
            print("end" + str(end))
            if start <= date <= end:
                return data[month][date_range]
    return 'B'


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis - stores mapping of Telegram username to Row Number on Google Spreadsheet.
redis_client = redis.StrictRedis(
    host='localhost', port=6379, db=0, decode_responses=True)

# Dictionaries storing the various mappings for the Telegram bot
# Maps student's telegram @username to row num and username
STUDENT_MAP = "STUDENT_MAP"
TUTOR_MAP = "TUTOR_MAP"  # Maps @username of staff to state ("no"/token)
# Maps the set of active tokens to a capacity, type, status and current students
TOKEN_MAP = "TOKEN_MAP"

# Google Spreadsheet
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    'attendance-bot-2020-21-44c478c22a71.json', scope)
gc = gspread.authorize(credentials)
wks1 = gc.open("Reflection Attendance AY 20/21 Sem 1").sheet1  # For Reflection


def get_user_id_or_username(update):
    """
    Function to get username or user ID depending on what is available.
    """
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if username:
        return username
    else:
        return user_id

##### Tutor #######


def start_session(update, context):
    """
    Function to start an attendance taking session.
    """
    # Store tutor usernames
    username = get_user_id_or_username(update)
    if not (redis_client.hexists(TUTOR_MAP, username)):
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
    token = generate_hash()

    if redis_client.hget(TUTOR_MAP, username) != "No":
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="A session is already running. Please use /stop_session to stop it")
        return

    redis_client.hdel(TOKEN_MAP, redis_client.hget(TUTOR_MAP, username))
    # Make tutor active. Store string value of token as value
    redis_client.hset(TUTOR_MAP, username, token)
    token_data = {
        'capacity': int(context.args[0]),
        'type': 'r',
        'active': True,
        'students': []
    }
    # Activate Token and store capacity
    redis_client.hset(TOKEN_MAP, token, json.dumps(token_data))
    context.bot.send_message(chat_id=update.message.chat_id, text=f'You have successfully started a Reflection '
                             f'Session. '
                             f'Your token is {token}. Please write it on a '
                             f'board to share it with students')


def stop_session(update, context):
    """
    Function to stop an attendance session.
    """
    username = get_user_id_or_username(update)
    if not (redis_client.hexists(TUTOR_MAP, username)):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    # stop the session
    token = redis_client.hget(TUTOR_MAP, username)
    if (token == "No") or (not json.loads(redis_client.hget(TOKEN_MAP, token))['active']):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="You've not started a session yet. Please send /start_session to start a session")
        return
    # Tutor is not active anymore
    redis_client.hset(TUTOR_MAP, username, "No")
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Your Reflection Session has successfully stopped. Thanks!")

    token_in_token_map = json.loads(redis_client.hget(TOKEN_MAP, token))
    token_in_token_map['active'] = False
    redis_client.hset(TOKEN_MAP, token, json.dumps(token_in_token_map))


def generate_hash():
    """
    Function to generate the attendance token hash.
    """
    token = hash(time.time()) % 100000000
    return token

##### Student ##########


def start(update, context):
    """
    Start function for the bot.
    """
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Welcome to CS1101S Cadet! This bot records your attendance for reflection sessions."
                                  "Please send /setup <student number> to get started.")


def setup(update, context):
    """
    Function to setup the username of student user and
    store it in the key-value database.
    """
    # check if no args
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Please enter your student number along with the '
                                                                      'command. Eg if your student number is '
                                                                      'A0123456X, enter /setup A0123456X')
        return
    # check if already registered
    username = get_user_id_or_username(update)
    if redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You're already signed up! Please wait for your"
                                                                      " tutor to give you a token to mark "
                                                                      "attendance")
        return
    # check if student can register for this module!
    student_no = context.args[0]
    try:
        refresh_gsp()  # refresh api auth
        cell = wks1.find(student_no)  # Look in reflection sessions
        row_num = cell.row
        student_details = {
            'row': row_num,
            'name': wks1.acell(f'A{row_num}').value
        }
        redis_client.hset(STUDENT_MAP, username, json.dumps(student_details))
        context.bot.send_message(chat_id=update.message.chat_id, text="You're successfully registered! Please wait "
                                                                      "for your tutor to give you an attendance token")
        # store in redis client
    except gspread.exceptions.CellNotFound:
        context.bot.send_message(chat_id=update.message.chat_id, text="Sorry! Your student number is not registered "
                                                                      "for this module. Please contact a staff "
                                                                      "member.")


def attend(update, context):
    """
    Function to mark attendance of bot user.
    """
    # check if no args
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Insufficient number of arguments. Please enter '
                                                                      'the token along with the /attend command')
        return
    # check if registered or not
    username = get_user_id_or_username(update)
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<student Number> to register")
        return
    # decide reflection or studio
    token = context.args[0]
    if not redis_client.hexists(TOKEN_MAP, token):  # Not active token
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Token doesn't exist or has expired. Please contact your tutor.")
        return
    refresh_gsp()  # refresh api auth

    col_name_reflect = get_week_ref()
    # check if already attended for current week
    row_name = json.loads(redis_client.hget(STUDENT_MAP, username))['row']
    # check reflection sheet
    val = wks1.acell(f'{col_name_reflect}{row_name}').value
    if val == "TRUE":
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Your attendance for this week has already been "
                                 "marked. Thanks!")
    else:
        # Token Logic
        curr_capacity = json.loads(
            redis_client.hget(TOKEN_MAP, token))['capacity']
        if curr_capacity == 0:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Cannot take attendance. Your class is full. Please contact tutor as "
                                     "someone may be trying to get undue points for attendance")
            return
        else:
            # set attendance
            wks1.update_acell(f'{col_name_reflect}{row_name}', 'TRUE')
            context.bot.send_message(chat_id=update.message.chat_id, text="Your attendance for this week has been "
                                     "successfully marked. Thanks!")
            token_map = json.loads(redis_client.hget(TOKEN_MAP, token))
            token_map['capacity'] -= 1
            redis_client.hset(TOKEN_MAP, token, json.dumps(
                token_map))  # reduce capacity
            return


def refresh_gsp():
    """
    Function to refresh Google Spreadsheet API token when it has expired.
    """
    global gc
    global credentials
    if credentials.access_token_expired:
        gc.login()


def help_func(update, context):
    """
    Function to generate help text.
    """
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Here are the available functions in the bot:\n"
                                  "For students: \n"
                                  "/setup <student number>: to register yourself.\n"
                                  "/attend <token> to mark your attendance. Token will be provided by cluster leader.\n"
                                  "/attendance_reflection to check your attendance for reflection sessions\n"
                                  "For avengers/tutors: \n"
                                  "/start_session <number of students> to mark the attendance for your group of "
                                  "students.\n"
                                  "/stop_session to stop your current running session.\n")

# (TODO) Review code for avenger vs student vs tutor reflection


def change_username(update, context):
    """
    Function to change the username of bot user.
    """
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Please enter your student number along with the '
                                                                      'command. Eg if your student number is '
                                                                      '123456789, enter /change_username 123456789')
    else:
        username = get_user_id_or_username(update)
        student_no = context.args[0]
        try:
            refresh_gsp()  # refresh api auth
            cell = wks1.find(student_no)  # Look in reflection sessions
            row_num = cell.row
            student_details = {
                'row': row_num,
                'name': wks2.acell(f'A{row_num}').value
            }
            redis_client.hset(STUDENT_MAP, username,
                              json.dumps(student_details))
            context.bot.send_message(
                chat_id=update.message.chat_id, text="You've successfully changed your username.")
            # store in redis client
        except gspread.exceptions.CellNotFound:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Sorry! Your student number is not registered "
                                          "for this module. Please contact a staff "
                                          "member.")


def attendance_reflection(update, context):
    """
    Function to know attendance so far for reflection sessions
    """
    # if not registered
    username = get_user_id_or_username(update)
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<Student Number> to register")
    else:  # iterate through columns of the row, checking for instances where the attendance is marked.
        refresh_gsp()  # refresh api auth
        row_num = json.loads(redis_client.hget(STUDENT_MAP, username))['row']
        weeks = []
        week_counter = 2
        for i in range(66, 78):
            col = chr(i)
            if wks1.acell(f'{col}{row_num}').value == '1':
                weeks.append("Week " + str(week_counter))
            week_counter += 1
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Our records indicate that you've so far attended reflection sessions for: "
                                      + print_arr(weeks) + ". Please contact a staff member if there is a discrepancy")


def cancel(update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Okay! Commenting canceled.")
    return ConversationHandler.END


def print_arr(arr):
    """
    Function to get the string version of an array in one line.
    """
    runner = ""
    for item in arr:
        runner += item + " "
    return runner


def init_data():
    """
    Setup initial data in the Redis database.
    """
    # Setup module/admin staff in Redis database
    with open('people.json') as people_json:
        data = json.load(people_json)
        for staff_member in data['staff']:
            if not redis_client.hexists(TUTOR_MAP, staff_member):
                redis_client.hset(TUTOR_MAP, staff_member, "No")
        for admin_member in data['admin']:
            if not redis_client.hexists(TUTOR_MAP, admin_member):
                redis_client.hset(TUTOR_MAP, admin_member, "No")


def main():
    """Start the bot"""
    # Create an event handler
    updater = Updater(os.environ.get('TELEKEY'), use_context=True)

    # Setup data in the Redis database
    init_data()

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('setup', setup))
    dp.add_handler(CommandHandler('attend', attend))
    dp.add_handler(CommandHandler('start_session', start_session))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    dp.add_handler(CommandHandler('change_username', change_username))
    dp.add_handler(CommandHandler('help', help_func))
    dp.add_handler(CommandHandler(
        'attendance_reflection', attendance_reflection))

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
