""" CS1101S Attendance Bot """
# Imports
import os
import json
import logging
from telegram.ext import Updater, CommandHandler
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


# Function to determine column based on date for Studio Spreadsheet
def get_week_stu():
    cur_time = time.asctime()
    li = cur_time.split()
    month = li[1]
    date = int(li[2])  # convert to integer for comparison later
    with open('acad_calendar_studio.json') as acad_calendar:
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
STUDENT_MAP = "STUDENT_MAP"  # Maps student's telegram @username to row num in spreadsheet
TUTOR_MAP = "TUTOR_MAP"  # Maps @username of staff to state ("no"/token)
TOKEN_MAP = "TOKEN_MAP"  # Maps the set of active tokens to an array capacity
AVENGER_MAP = "AVENGER_MAP"  # Maps @username of avenger to state ("no"/token)
TOKEN_TYPE_MAP = "TOKEN_TYPE"  # Maps the set of active tokens to type, which is either "r" or "s"

# Google Spreadsheet
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('CS1101S Bot-99365efd2073.json', scope)
gc = gspread.authorize(credentials)
wks1 = gc.open("CS1101S Reflection Attendance").sheet1  # For Reflection
wks2 = gc.open("CS1101S Studio Attendance").sheet1  # For studio
col_name_attend = get_week_stu()
col_name_comment = chr(ord(col_name_attend) + 1)
col_name_reflect = get_week_ref()

"""
Function to get username or user ID depending on what is available.
"""


def get_user_id_or_username(update):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if username:
        return username
    else:
        return user_id


##### Tutor #######

"""
Function to start an attendance session.
"""


def start_session(update, context):
    # Store tutor usernames
    username = get_user_id_or_username(update)
    if not (redis_client.hexists(TUTOR_MAP, username) or redis_client.hexists(AVENGER_MAP, username)):
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
    if redis_client.hexists(TUTOR_MAP, username):
        if redis_client.hget(TUTOR_MAP, username) != "No":
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="A session is already running. Please use /stop_session to stop it")
            return

        redis_client.hset(TUTOR_MAP, username, token)  # Make tutor active. Store string value of token as value
        redis_client.hset(TOKEN_MAP, token, int(context.args[0]))  # Activate Token and store capacity
        redis_client.hset(TOKEN_TYPE_MAP, token, "r")  # Reflection type
        context.bot.send_message(chat_id=update.message.chat_id, text=f'You have successfully started a Reflection '
                                                                      f'Session. '
                                                                      f'Your token is {token}. Please write it on a '
                                                                      f'board to share it with students')
    else:  # avenger
        if redis_client.hget(AVENGER_MAP, username) != "No":
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="A session is already running. Please use /stop_session to stop it")
            return

        redis_client.hset(AVENGER_MAP, username, token)
        redis_client.hset(TOKEN_MAP, token, int(context.args[0]))
        redis_client.hset(TOKEN_TYPE_MAP, token, "s")  # Studio type
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text=f'You have successfully started a Studio Session. '
                                      f'Your token is {token}. Please write it on a board to share it with students')


"""
Function to stop an attendance session.
"""


def stop_session(update, context):
    username = get_user_id_or_username(update)
    if not (redis_client.hexists(TUTOR_MAP, username) or redis_client.hexists(AVENGER_MAP, username)):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    if redis_client.hget(TUTOR_MAP, username) == "No" or redis_client.hget(AVENGER_MAP, username) == "No":
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="You've not started a session yet. Please send /start_session to start a session")
        return
    # stop the session
    if redis_client.hexists(TUTOR_MAP, username):
        token = redis_client.hget(TUTOR_MAP, username)
        redis_client.hdel(TOKEN_MAP, token)  # Deletes the session completely.
        redis_client.hset(TUTOR_MAP, username, "No")  # Tutor is not active anymore
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Your Reflection Session has successfully stopped. Thanks!")
    else:
        token = redis_client.hget(AVENGER_MAP, username)
        redis_client.hdel(TOKEN_MAP, token)
        redis_client.hdel(TOKEN_TYPE_MAP, token)
        redis_client.hset(AVENGER_MAP, username, "No")
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Your Studio Session has successfully stopped. Thanks!")


"""
Function to generate the attendance token hash.
"""


def generate_hash():
    token = hash(time.time()) % 100000000
    return token


##### Student ##########

"""
Start function for the bot.
"""


def start(update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Welcome to CS1101S Cadet! This bot records your attendance for reflection sessions."
                                  "Please send /setup <student number> to get started.")


"""
Function to setup the username of student user and
store it in the key-value database. 
"""


def setup(update, context):
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
        global gc
        global credentials
        if credentials.access_token_expired:
            gc.login()
        cell = wks1.find(student_no)  # Look in reflection sessions
        row_num = cell.row
        redis_client.hset(STUDENT_MAP, username, row_num)
        context.bot.send_message(chat_id=update.message.chat_id, text="You're successfully registered! Please wait "
                                                                      "for your tutor to give you an attendance token")
        # store in redis client
    except gspread.exceptions.CellNotFound:
        context.bot.send_message(chat_id=update.message.chat_id, text="Sorry! Your student number is not registered "
                                                                      "for this module. Please contact a staff "
                                                                      "member.")


"""
Function to mark attendance of bot user.
"""


def attend(update, context):
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
    tipe = redis_client.hget(TOKEN_TYPE_MAP, token)
    global gc
    global credentials
    if credentials.access_token_expired:
        gc.login()
    if tipe == "r":  # reflection session
        # check if already attended for current week
        row_name = redis_client.hget(STUDENT_MAP,
                                     username)  # (TODO) make sure the row number are same for each student in both the different sheets
        val = wks1.acell(f'{col_name_reflect}{row_name}').value  # check reflection sheet
        if val == 1:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Your attendance for this week has already been"
                                          "marked. Thanks!")
        else:
            # Token Logic
            token = context.args[0]
            if not redis_client.hexists(TOKEN_MAP, token):  # Not active token
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
                wks1.update_acell(f'{col_name_reflect}{row_name}', '1')
                context.bot.send_message(chat_id=update.message.chat_id, text="Your attendance for this week has been "
                                                                              "successfully marked. Thanks!")
                redis_client.hset(TOKEN_MAP, token, curr_capacity - 1)  # reduce capacity
                return

    else:  # studio session
        # check if already attended for current week
        row_name = redis_client.hget(STUDENT_MAP,
                                     username)  # (TODO) make sure the row number are same for each student in both
        # the different sheets
        val = wks2.acell(f'{col_name_attend}{row_name}').value
        if val == 1:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Your attendance for this week has already been"
                                          "marked. Thanks!")
        else:
            if not redis_client.hexists(TOKEN_MAP, token):  # Not active token
                context.bot.send_message(chat_id=update.message.chat_id,
                                         text="Token doesn't exist or has expired. Please contact your tutor.")
                return
            curr_capacity = int(redis_client.hget(TOKEN_MAP, token))
            if curr_capacity == 0:
                context.bot.send_message(chat_id=update.message.chat_id,
                                         text="Cannot take attendance. Your class is full. Please contact Avenger as "
                                              "someone may be trying to get undue points for attendance")
                return
            else:
                # set attendance
                wks2.update_acell(f'{col_name_attend}{row_name}', '1')
                context.bot.send_message(chat_id=update.message.chat_id, text="Your attendance for this week has been "
                                                                              "successfully marked. Thanks!")
                redis_client.hset(TOKEN_MAP, token, curr_capacity - 1)  # reduce capacity
                return


"""
Function to generate help text.
"""


def help_func(update, context):
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Here are the available functions in the bot:\n"
                                  "/setup <student number>: to register yourself.\n"
                                  "/attend <token> to mark your attendance. Token will be provided by cluster leader.\n"
                                  "/feedback <feedback> to give feedback or report bugs to the developers.\n"
                                  "/start_session <number of students> to mark the attendance for your group of "
                                  "avengers.\n "
                                  "/stop_session to stop your current running session.")


"""
Function to change the username of bot user.
"""

# def change_username(update, context):  # (TODO) Review code for avenger vs student vs tutor reflection
#     # just extract username and update in reddis client. Ask chai: can we do is?
#     if len(context.args) == 0:
#         context.bot.send_message(chat_id=update.message.chat_id, text='Please enter your student number along with the '
#                                                                       'command. Eg if your student number is '
#                                                                       '123456789, enter /change_username 123456789')
#         return
#     username = get_user_id_or_username()
#     student_no = context.args[0]
#     cell = wks.find(student_no)
#     row_num = cell.row
#     redis_client.hset(STUDENT_MAP, username, row_num)
#     context.bot.send_message(chat_id=update.message.chat_id, text="You're successfully registered! Please wait "
#                                                                   "for your cluster leader to give you an attendance "
#                                                                   "token")
#     return
#

"""
Function to give feedback to the developers.
"""
# def feedback(update, context):


"""
Function to know attendance so far for studio sessions
"""

# def my_attendance_studio(update, context):
#     # if not registered
#     username = get_user_id_or_username(update)
#     if not redis_client.hexists(STUDENT_MAP, username):
#         context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
#                                                                       "<student Number> to register")
#     else:
#         row_num = redis_client.hget(STUDENT_MAP, username)


"""
Function to know attendance so far for reflection sessions
"""


def attendance_reflection(update, context):
    # if not registered
    username = get_user_id_or_username(update)
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<student Number> to register")
    else:
        row_num = redis_client.hget(STUDENT_MAP, username)
        weeks = []
        week_counter = 2
        for i in range(66, 78):
            col = chr(i)
            if wks1.acell(f'{col}{row_num}').value == u"\u2713":
                weeks.append("Week " + str(week_counter))
                week_counter += 1
        print(weeks)
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Our records indicate that you've so far attended reflection sessions for: " + print_arr(
                                     weeks))


"""
Function to get the string version of an array in one line. 
"""


def print_arr(arr):
    runner = ""
    for item in arr:
        runner += item + " "
    print(runner)
    return runner


def main():
    """Start the bot"""
    # Create an event handler, # (TODO) hide key
    updater = Updater('***REMOVED***', use_context=True)

    # Setup module/admin staff in Redis database
    with open('people.json') as people_json:
        data = json.load(people_json)
        for staff_member in data['staff']:
            redis_client.hset(TUTOR_MAP, staff_member, "No")
        for admin_member in data['admin']:
            redis_client.hset(TUTOR_MAP, admin_member, "No")
        for avenger in data['avenger']:
            redis_client.hset(AVENGER_MAP, avenger, "No")
        redis_client.hset(AVENGER_MAP, "raivatshah", "No")  # for testing.

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('setup', setup))
    dp.add_handler(CommandHandler('attend', attend))
    dp.add_handler(CommandHandler('start_session', start_session))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    # dp.add_handler(CommandHandler('change_username', change_username))
    dp.add_handler(CommandHandler('help', help_func))
    dp.add_handler(CommandHandler('attendance_reflection', attendance_reflection))

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
