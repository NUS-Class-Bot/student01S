""" CS1101S Attendance Bot """
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

# Constants for conversation handler
SELECT_STUDENT, ENTER_COMMENT = range(2)

# Redis - stores mapping of Telegram username to Row Number on Google Spreadsheet.
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Dictionaries storing the various mappings for the Telegram bot
STUDENT_MAP = "STUDENT_MAP"  # Maps student's telegram @username to row num and username
USERNAME_MAP = "USERNAME_MAP" # Maps student's name to their telegram username/ID
TUTOR_MAP = "TUTOR_MAP"  # Maps @username of staff to state ("no"/token)
TOKEN_MAP = "TOKEN_MAP"  # Maps the set of active tokens to a capacity, type, status and current students
AVENGER_MAP = "AVENGER_MAP"  # Maps @username of avenger to token number

# for Feedback
if not redis_client.hexists(TOKEN_MAP, "feedback"):
    redis_client.hset(TOKEN_MAP, "feedback", json.dumps({'capacity': 2, 'active': True, 'type': 'feedback', 'students': []}))

# Google Spreadsheet
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('CS1101S Bot-99365efd2073.json', scope)
gc = gspread.authorize(credentials)
wks1 = gc.open("CS1101S Reflection Attendance").sheet1  # For Reflection
wks2 = gc.open("CS1101S Studio Attendance").sheet1  # For studio
wk3 = gc.open("CS1101S Bot Feedback").sheet1  # For Bot Feedback
# wk4 = gc.open("CS1101S Avenger Feedback").sheet1 # For Avenger Feedback, disabled because this is giving error

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
    Function to start an attendance session.
    """
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

        redis_client.hdel(TOKEN_MAP, redis_client.hget(TUTOR_MAP, username))
        redis_client.hset(TUTOR_MAP, username, token)  # Make tutor active. Store string value of token as value
        token_data = {
            'capacity': int(context.args[0]),
            'type': 'r',
            'active': True,
            'students': []
        }
        redis_client.hset(TOKEN_MAP, token, json.dumps(token_data))  # Activate Token and store capacity
        context.bot.send_message(chat_id=update.message.chat_id, text=f'You have successfully started a Reflection '
                                                                      f'Session. '
                                                                      f'Your token is {token}. Please write it on a '
                                                                      f'board to share it with students')
    else:  # avenger
        avenger_token = redis_client.hget(AVENGER_MAP, username)
        if avenger_token != "No" and json.loads(redis_client.hget(TOKEN_MAP, avenger_token))['active']:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="A session is already running. Please use /stop_session to stop it")
            return

        redis_client.hdel(TOKEN_MAP, redis_client.hget(AVENGER_MAP, username))
        redis_client.hset(AVENGER_MAP, username, token)
        token_data = {
            'capacity': int(context.args[0]),
            'type': 's',
            'active': True,
            'students': []
        }
        redis_client.hset(TOKEN_MAP, token, json.dumps(token_data))
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text=f'You have successfully started a Studio Session. '
                                      f'Your token is {token}. Please write it on a board to share it with students')

def stop_session(update, context):
    """
    Function to stop an attendance session.
    """
    username = get_user_id_or_username(update)
    if not (redis_client.hexists(TUTOR_MAP, username) or redis_client.hexists(AVENGER_MAP, username)):
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    # stop the session
    if redis_client.hexists(TUTOR_MAP, username):
        token = redis_client.hget(TUTOR_MAP, username)
        if (token == "No") or (not json.loads(redis_client.hget(TOKEN_MAP, token))['active']):
            context.bot.send_message(chat_id=update.message.chat_id,
                                 text="You've not started a session yet. Please send /start_session to start a session")
            return
        redis_client.hset(TUTOR_MAP, username, "No")  # Tutor is not active anymore
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Your Reflection Session has successfully stopped. Thanks!")
    else:
        token = redis_client.hget(AVENGER_MAP, username)
        if (token == "No") or (not json.loads(redis_client.hget(TOKEN_MAP, token))['active']):
            context.bot.send_message(chat_id=update.message.chat_id,
                                 text="You've not started a session yet. Please send /start_session to start a session")
            return
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Your Studio Session has successfully stopped. Thanks!")
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
        global gc
        global credentials
        if credentials.access_token_expired:
            gc.login()
        cell = wks1.find(student_no)  # Look in reflection sessions
        row_num = cell.row
        student_details = {
            'row': row_num,
            'name': wks2.acell(f'A{row_num}').value
        }
        redis_client.hset(STUDENT_MAP, username, json.dumps(student_details))
        redis_client.hset(USERNAME_MAP, student_details['name'], username)
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
    token_type = json.loads(redis_client.hget(TOKEN_MAP, token))['type']
    global gc
    global credentials
    if credentials.access_token_expired:
        gc.login()
    if token_type == "r":  # reflection session
        col_name_reflect = get_week_ref()
        # check if already attended for current week
        row_name = json.loads(redis_client.hget(STUDENT_MAP, username))['row']  # (TODO) make sure the row number are same for each student in both the different sheets
        val = wks1.acell(f'{col_name_reflect}{row_name}').value  # check reflection sheet
        if val == "1":
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Your attendance for this week has already been "
                                          "marked. Thanks!")
        else:
            # Token Logic
            curr_capacity = json.loads(redis_client.hget(TOKEN_MAP, token))['capacity']
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
                token_map = json.loads(redis_client.hget(TOKEN_MAP, token))
                token_map['capacity'] -= 1
                redis_client.hset(TOKEN_MAP, token, json.dumps(token_map))  # reduce capacity
                return

    elif token_type == "s":  # studio session
        # check if already attended for current week
        col_name_attend = get_week_stu()
        col_name_comment = chr(ord(col_name_attend) + 1)
        row_name = json.loads(redis_client.hget(STUDENT_MAP, username))['row']  # (TODO) make sure the row number are same for each student in both
        # the different sheets
        val = wks2.acell(f'{col_name_attend}{row_name}').value
        if val == "1":
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Your attendance for this week has already been "
                                          "marked. Thanks!")
        else:
            if not redis_client.hexists(TOKEN_MAP, token):  # Not active token
                context.bot.send_message(chat_id=update.message.chat_id,
                                         text="Token doesn't exist or has expired. Please contact your tutor.")
                return
            curr_capacity = json.loads(redis_client.hget(TOKEN_MAP, token))['capacity']
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
                token_map = json.loads(redis_client.hget(TOKEN_MAP, token))
                student_list = token_map['students'].copy()
                student_list.append(json.loads(redis_client.hget(STUDENT_MAP, username))['name'])
                token_map['capacity'] -= 1
                token_map['students'] = student_list
                redis_client.hset(TOKEN_MAP, token, json.dumps(token_map))  # reduce capacity
                return

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
                                  "/attendance_studio to check your attendance for studio sessions\n"
                                  "For avengers/tutors: \n"
                                  "/start_session <number of students> to mark the attendance for your group of "
                                  "avengers.\n"
                                  "/stop_session to stop your current running session."
                                  "For all: \n"
                                  "/feedback <feedback> to give feedback or report bugs to the developers.\n")

def change_username(update, context):  # (TODO) Review code for avenger vs student vs tutor reflection
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
            global gc
            global credentials
            if credentials.access_token_expired:
                gc.login()
            cell = wks1.find(student_no)  # Look in reflection sessions
            row_num = cell.row
            student_details = {
                'row': row_num,
                'name': wks2.acell(f'A{row_num}').value
            }
            redis_client.hset(STUDENT_MAP, username, json.dumps(student_details))
            redis_client.hset(USERNAME_MAP, student_details['name'], username)
            context.bot.send_message(chat_id=update.message.chat_id, text="You've successfully changed your username.")
            # store in redis client
        except gspread.exceptions.CellNotFound:
            context.bot.send_message(chat_id=update.message.chat_id,
                                     text="Sorry! Your student number is not registered "
                                          "for this module. Please contact a staff "
                                          "member.")

def bot_feedback(update, context):
    """
    Function to give feedback to the developers.
    """
    if len(context.args) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text='Please send your valuable feedback along with '
                                                                      'this /feedback command, all in the same '
                                                                      'message')
    else:
        name = update.message.from_user.first_name
        username = get_user_id_or_username(update)
        global gc
        global credentials
        if credentials.access_token_expired:
            gc.login()
        feedback_token = json.loads(redis_client.hget(TOKEN_MAP, "feedback"))
        row = feedback_token['capacity']
        wk3.update_acell("A" + row, name)
        wk3.update_acell("B" + row, username)
        wk3.update_acell("C" + row, print_arr(context.args))
        feedback_token['capacity'] += 1
        redis_client.hset(TOKEN_MAP, "feedback", json.dumps(feedback_token))  # update row num for other feedback
        context.bot.send_message(chat_id=update.message.chat_id, text="Thank you so much for your valuable feedback!")

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
        global gc
        global credentials
        if credentials.access_token_expired:
            gc.login()
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

def attendance_studio(update, context):
    """
    Function to know attendance so far for studio sessions
    """
    # if not registered
    username = get_user_id_or_username(update)
    if not redis_client.hexists(STUDENT_MAP, username):
        context.bot.send_message(chat_id=update.message.chat_id, text="You've not registered yet. Please send /setup "
                                                                      "<Student Number> to register")
    else:  # iterate through columns of the row, checking for instances where the attendance is marked.
        global gc
        global credentials
        if credentials.access_token_expired:
            gc.login()
        row_num = json.loads(redis_client.hget(STUDENT_MAP, username))['row']
        weeks = []
        week_counter = 2
        for i in range(67, 90, 2):
            col = chr(i)
            if wks2.acell(f'{col}{row_num}').value == '1':
                weeks.append("Week " + str(week_counter))
                week_counter += 1
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="Our records indicate that you've so far attended studio sessions for: " +
                                      print_arr(weeks) + ". Please contact a staff member if there is a discrepancy")

def comment(update, context):
    """
    Function to comment on students who attended tutorial
    """
    username = get_user_id_or_username(update)
    token = redis_client.hget(AVENGER_MAP, username)
    students = json.loads(redis_client.hget(TOKEN_MAP, token))['students']
    if len(students) == 0:
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text="No students have signed up yet!")
        return ConversationHandler.END    
    reply_keyboard = [[i] for i in students]
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Select a student from the list below. Type /cancel to cancel the process.",
                             reply_markup=ReplyKeyboardMarkup(reply_keyboard))
    return SELECT_STUDENT

def select_student(update, context):
    """
    This function is reached after the student name has been entered.
    """
    student = update.message.text
    context.user_data['student'] = redis_client.hget(USERNAME_MAP, student)
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Okay, enter the comment for this student.")
    return ENTER_COMMENT

def enter_comment(update, context):
    """
    This function is reached after the comment has been entered.
    """
    comment = update.message.text
    student = context.user_data['student']
    col_name_comment = chr(ord(get_week_stu()) + 1)
    row_name = json.loads(redis_client.hget(STUDENT_MAP, student))['row']
    wks2.update_acell(f'{col_name_comment}{row_name}', comment)
    context.bot.send_message(chat_id=update.message.chat_id,
                             text="Okay! Comment has been added.")
    return ConversationHandler.END

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
    dp.add_handler(CommandHandler('change_username', change_username))
    dp.add_handler(CommandHandler('help', help_func))
    dp.add_handler(CommandHandler('attendance_reflection', attendance_reflection))
    dp.add_handler(CommandHandler('attendance_studio', attendance_studio))
    dp.add_handler(CommandHandler('bot_feedback', bot_feedback))

    # Create a conversation handler for commenting
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('comment', comment)],
        states={
            SELECT_STUDENT: [MessageHandler(Filters.text, select_student)],
            ENTER_COMMENT: [MessageHandler(Filters.text, enter_comment)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(conv_handler)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
