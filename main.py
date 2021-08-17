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
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis - stores mapping of Telegram username to Row Number on Google Spreadsheet.
redis_client = redis.StrictRedis(
    host='localhost', port=6379, db=0, decode_responses=True)

# Dictionaries storing the various mappings for the Telegram bot
# Maps student's telegram @username to row num and username
STUDENT_MAP = "STUDENT_MAP"
TUTOR_MAP = "TUTOR_MAP"  # Maps @username of staff to token (collection of token number and whether it is active)
# Maps the set of active tokens to a capacity, type, status and current students
TOKEN_MAP = "TOKEN_MAP"

# Google Spreadsheet
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    'attend.json', scope)
gc = gspread.authorize(credentials)
try:
    wks1 = gc.open("CS1101S Reflection Attendance AY 21/22 Sem 1").sheet1  # For Reflection
except gspread.exceptions.GSpreadException:
    print('Error in opening the sheet!')

# Helper functions to get username and user ID
# Currently we are checking tutor existence through usernames since we have easy access to them,
# and user IDs for students. We can add a mechanism later to swap tutor usernames for user IDs in the `start_session` function.
# TODO: Add mechanism for swapping tutor usernames for user IDs.

def get_user_id(update):
    return update.message.from_user.id

def get_username(update):
    return update.message.from_user.username

##### Tutor #######


def start_session(update, context):
    """
    Function to start an attendance taking session.
    """
    username = get_username(update)

    # Check whether username is for a valid tutor
    if not (redis_client.hexists(TUTOR_MAP, username)):
        update.message.reply_text("Sorry! You're not registered as a staff member and hence cannot use this command")
        return 

    # Check whether attendance capacity is supplied
    if len(context.args) == 0:
        update.message.reply_text("Insufficient number of arguments. Please enter number of students along with "
                                  "the /start_session command")
        return

    # Check whether the capacity is positive
    if int(context.args[0]) <= 0:
        update.message.reply_text("Number of students must be greater than 0.")
        return

    # Generate token
    token = generate_hash()

    # Return error message if a session is already running
    tutor_token = json.loads(redis_client.hget(TUTOR_MAP, username))
    if tutor_token['active']:
        update.message.reply_text("A session is already running. Please use /stop_session to stop it")
        return

    # Delete previously existing token for tutor
    redis_client.hdel(TOKEN_MAP, tutor_token['token'])
    
    # Make tutor active. Store string value of token as value
    tutor_token = {
        'token': token,
        'active': True,
    }
    redis_client.hset(TUTOR_MAP, username, json.dumps(tutor_token))

    # Activate Token and store capacity
    token_data = {
        'capacity': int(context.args[0]),
        'active': True,
    }
    redis_client.hset(TOKEN_MAP, token, json.dumps(token_data))

    update.message.reply_text(f'You have successfully started a Reflection '
                              f'Session. '
                              f'Your token is {token}. Please write it on a '
                              f'board to share it with students')


def stop_session(update, context):
    """
    Function to stop an attendance session.
    """
    username = get_username(update)

    # Check whether username is for a valid tutor
    if not (redis_client.hexists(TUTOR_MAP, username)):
        update.message.reply_text("Sorry! You're not registered as a staff member and hence cannot use this command")
        return
    
    # Get the existing token for tutor
    tutor_token = json.loads(redis_client.hget(TUTOR_MAP, username))

    # If no token exists means no attendance session exists
    if not tutor_token['active']:
        update.message.reply_text("You've not started a session yet. Please send /start_session to start a session")
        return
    
    # Make token inactive for tutor
    tutor_token['active'] = False
    redis_client.hset(TUTOR_MAP, username, json.dumps(tutor_token))
    update.message.reply_text("Your Reflection Session has successfully stopped. Thanks!")

    # Set token to inactive
    token = tutor_token['token']
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
    update.message.reply_text("Welcome to CS1101S Cadet! This bot records your attendance for reflection sessions."
                              "Please send /setup <student number> to get started.")


def setup(update, context):
    """
    Function to setup the username of student user and
    store it in the key-value database.
    """
    # check if no args
    if len(context.args) == 0:
        update.message.reply_text('Please enter your student number along with the '
                                  'command. Eg if your student number is '
                                  'A0123456X, enter /setup A0123456X')
        return
    
    user_id = get_user_id(update)

    # check if already registered
    if redis_client.hexists(STUDENT_MAP, user_id):
        update.message.reply_text("You're already signed up! Please wait for your"
                                  " tutor to give you a token to mark "
                                  "attendance")
        return
    
    # check if student can register for this module
    student_no = context.args[0]
    try:
        refresh_gsp()  # refresh api auth
        cell = wks1.find(student_no)  # Look in reflection sessions
        if not cell:
            raise gspread.exceptions.CellNotFound
        row_num = cell.row
        student_details = {
            'row': row_num,
            'name': wks1.acell(f'A{row_num}').value
        }
        # store in redis client
        redis_client.hset(STUDENT_MAP, user_id, json.dumps(student_details))
        update.message.reply_text("You're successfully registered! Please wait "
                                  "for your tutor to give you an attendance token")
    except gspread.exceptions.CellNotFound:
        update.message.reply_text("Sorry! Your student number is not registered "
                                  "for this module. Please contact a staff member.")
    except:
        update.message.reply_text("There was some issue in registration, please try again.")

def decrease_token_capacity(token_data_and_token):
    """
    Helper function to decrease token capacity if value is returned.
    """
    # No result was returned
    if not token_data_and_token:
        return
    
    # Update token capacity
    token_data = token_data_and_token[0]
    token = token_data_and_token[1]
    token_data['capacity'] -= 1
    redis_client.hset(TOKEN_MAP, token, json.dumps(token_data))  # reduce capacity

def attend_async(update, context):
    """
    Helper function to run part of the `attend` function asynchronously.
    """
    # check if no args
    if len(context.args) == 0:
        update.message.reply_text('Insufficient number of arguments. Please enter '
                                  'the token along with the /attend command')
        return None
    
    username = get_user_id(update)

    # check if registered or not
    if not redis_client.hexists(STUDENT_MAP, username):
        update.message.reply_text("You've not registered yet. Please send /setup "
                                  "<student Number> to register")
        return None
    
    # Get token
    token = context.args[0]

    # Check if token is active
    if not redis_client.hexists(TOKEN_MAP, token):
        update.message.reply_text("Token doesn't exist or has expired. Please contact your tutor.")
        return None 
    
    token_data = json.loads(redis_client.hget(TOKEN_MAP, token))
    if not token_data['active']:
        update.message.reply_text("Token doesn't exist or has expired. Please contact your tutor.")
        return None

    refresh_gsp()  # refresh api auth

    # Get column name for the current week
    col_name_reflect = get_week_ref()
    # check if already attended for current week
    row_name = json.loads(redis_client.hget(STUDENT_MAP, username))['row']

    # check if attendance already marked
    try:
        val = wks1.acell(f'{col_name_reflect}{row_name}').value
    except:
        update.message.reply_text("There was some issue in marking attendance, please try again.")
        return
    if val == "TRUE":
        update.message.reply_text("Your attendance for this week has already been "
                                  "marked. Thanks!")
        return None
    
    # Check if token has maxed out its capacity
    curr_capacity = token_data['capacity']
    if curr_capacity == 0:
        update.message.reply_text("Cannot take attendance. Your class is full. Please contact tutor as "
                                  "someone may be trying to get undue points for attendance")
        return None
    
    # update attendance
    try:
        wks1.update_acell(f'{col_name_reflect}{row_name}', 'TRUE')
    except:
        update.message.reply_text("There was some issue in marking attendance, please try again.")
        return

    update.message.reply_text("Your attendance for this week has been successfully marked. Thanks!")
    return (token_data, token)

def attend(update, context):
    """
    Function to mark attendance of bot user.
    """
    context.dispatcher.run_async(
        attend_async,
        update,
        context,
        update=update
    ).add_done_callback(decrease_token_capacity)


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
    update.message.reply_text("Here are the available functions in the bot:\n"
                              "For students: \n"
                              "/setup <student number>: to register yourself.\n"
                              "/attend <token> to mark your attendance. Token will be provided by cluster leader.\n"
                              "/attendance_reflection to check your attendance for reflection sessions\n"
                              "For avengers/tutors: \n"
                              "/start_session <number of students> to mark the attendance for your group of "
                              "students.\n"
                              "/stop_session to stop your current running session.\n")

def change_username(update, context):
    """
    Function to change the username of bot user.
    """
    if len(context.args) == 0:
        update.message.reply_text('Please enter your student number along with the '
                                  'command. Eg if your student number is '
                                  '123456789, enter /change_username 123456789')
        return

    user_id = get_user_id(update)
    student_no = context.args[0]
    try:
        refresh_gsp()  # refresh api auth
        # Find row number in reflection session sheet
        cell = wks1.find(student_no)
        if not cell:
            raise gspread.exceptions.CellNotFound
        row_num = cell.row
        student_details = {
            'row': row_num,
            'name': wks1.acell(f'A{row_num}').value
        }
        # Map new user ID to row number
        redis_client.hset(STUDENT_MAP, user_id,
                            json.dumps(student_details))
        update.message.reply_text("You've successfully changed your username.")
    except gspread.exceptions.CellNotFound:
        update.message.reply_text("Sorry! Your student number is not registered "
                                  "for this module. Please contact a staff "
                                  "member.")
    except:
        update.message.reply_text("There was some issue in registration, please try again.")


def attendance_reflection(update, context):
    """
    Function to know attendance so far for reflection sessions
    """

    username = get_user_id(update)

    # Check if student is registered
    if not redis_client.hexists(STUDENT_MAP, username):
        update.message.reply_text("You've not registered yet. Please send /setup <Student Number> to register")
        return

    refresh_gsp()  # refresh api auth

    # iterate through columns of the row, checking for instances where the attendance is marked.
    row_num = json.loads(redis_client.hget(STUDENT_MAP, username))['row']
    try:
        cells = wks1.range(f'B{row_num}:M{row_num}')
    except gspread.exceptions.GSpreadException:
        update.message.reply_text("There was some issue in checking attendance, please try again.")
        return
    # filter the 'FALSE' values out
    cells = map(lambda index_cell: f'Week {index_cell[0] + 2}' if index_cell[1].value == 'TRUE' else 'FALSE', enumerate(cells))
    cells = list(filter(lambda x : x != 'FALSE', cells))

    update.message.reply_text(f"Our records indicate that you've so far attended reflection sessions for:\n\n{print_arr(cells)}\n\n" 
                              "Please contact a staff member if there is a discrepancy.")

def print_arr(arr):
    """
    Function to get the string version of an array in one line.
    """
    return "\n".join(arr)


def init_data():
    """
    Setup initial data in the Redis database.
    """
    # Initial token data for tutors and staff
    tutor_token = json.dumps({
        'token': 'No',
        'active': False
    })

    # Setup module/admin staff in Redis database
    with open('people.json') as people_json:
        data = json.load(people_json)
        for staff_member in data['staff']:
            if not redis_client.hexists(TUTOR_MAP, staff_member):
                print('added ' + staff_member + ' to tutor map')
                redis_client.hset(TUTOR_MAP, staff_member, tutor_token)
        for admin_member in data['admin']:
            if not redis_client.hexists(TUTOR_MAP, admin_member):
                redis_client.hset(TUTOR_MAP, admin_member, tutor_token)

def main():
    """Start the bot"""
    # Create an event handler
    updater = Updater(os.environ.get('TELEKEY'), use_context=True)

    # Setup data in the Redis database
    init_data()

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('start', start, run_async=True))
    dp.add_handler(CommandHandler('setup', setup, run_async=True))
    dp.add_handler(CommandHandler('attend', attend))
    dp.add_handler(CommandHandler('start_session', start_session, run_async=True))
    dp.add_handler(CommandHandler('stop_session', stop_session, run_async=True))
    dp.add_handler(CommandHandler('change_username', change_username, run_async=True))
    dp.add_handler(CommandHandler('help', help_func, run_async=True))
    dp.add_handler(CommandHandler('attendance_reflection', attendance_reflection, run_async=True))

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
