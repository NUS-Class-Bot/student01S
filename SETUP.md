# NUS Class Bot - Setup Guide

Project Supervisor: A/P [Martin Henz](https://github.com/martin-henz). Project Advisor: [Tobias Wrigstad](https://github.com/TobiasWrigstad)

Student Developers: [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah). Co-Founders: [Advay Pal](https://github.com/advaypal), [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah)

This guide is for bot administrators to setup and deploy the bot from scratch, so it can continue making attendance simpler in the future!

## Setting up a Google Sheet for Attendance

A Google Sheet serves as persistent storage for attendance data and is in the format of a table. Each student is an entry in the table and is uniquely identified by their matriculation numbers. There are exactly 13 columns, one for the student number and 12 for indicating the attendance in weeks 2 to 13, inclusive. A sample is shown in the following image: 

<img width="1369" alt="Sample Attendance Sheet" src="https://user-images.githubusercontent.com/29497717/174571887-10da7e42-97d1-4303-9ed7-bea6a8917c89.png">

Before the start of the semester, make sure you add all the matriculation numbers to the Student Numbers column. This is to whitelist access to the bot so that no one can arbitrarily sign up to use the bot. 

Once the above is done, we need to give the bot access to this spreadsheet.

### Setting up Google Sheet credentials for the bot

* Go to [https://console.developers.google.com][Google Developers Console] and setup a new project 
* Click on the "Enable APIs and Services Button":

<img width="890" alt="Screenshot 2022-06-20 at 3 11 42 PM" src="https://user-images.githubusercontent.com/29497717/174574095-a581660b-343e-4d0f-a93a-710b087ef6b1.png">

* You will be redirected to the API library. Enable both the **Google Drive API** and the **Google Sheets API**.
* Go to the credentials page from the left sidebar menu and click on "create credentials" -> "service account" 
* Fill out the form, as shown here and copy the email address: 

<img width="583" alt="Screenshot 2022-06-20 at 3 16 21 PM" src="https://user-images.githubusercontent.com/29497717/174574935-6b442a30-74f0-4e42-b6c0-90dd1296dde6.png">

* Once the service account is created, click on it and go to the keys tab:

<img width="575" alt="Screenshot 2022-06-20 at 3 18 38 PM" src="https://user-images.githubusercontent.com/29497717/174575381-b2609a92-1502-4ad3-a84b-e3b4ae0e0b03.png">

* Click on "add key" -> "create new key" -> "json" 
* A new JSON file will be downloaded on your computer. Rename it to `attend.json` and copy it to the `records/` directory. 
* Share the google spreadsheet with the bot's email address copied earlier (available as "client email address" in the `attend.json` file).

## Updating the Academic Calendar

When taking attendance from students, the bot automatically maps the day to the relevant week column on the attendance sheet. The mapping between date of entry and the sheet column is done as JSONs in `records/acad_calendar.json`. The format of the JSON file is as follows, but you can also take a look at the existing file to get an idea:

```
{
  "Aug": {
    "1-4": <SHEET COLUMN>,  # from 1st to 4th August inclusive
    "5-10": <SHEET COLUMN>, # from 5th to 10th August inclusive
    ...
  },
  "Sep": {
    "1-4": <SHEET COLUMN>,
    ...
  },
  "Oct": {
    "1-4": <SHEET COLUMN>
    ...
  },
  "Nov": {
    "1-4": <SHEET COLUMN>,
    ...
  },
  ...
}
```

## Updating the Telegram access roles

Currently the Telegram usernames which are assigned as reflection tutors and bot administrators are hardcoded in a `records/people.json` file. Only usernames mentioned in this file can access the tutor functions of the but (such as starting and stopping attendance sessions). **It is for this reason that tutors should not change their Telegram usernames throughout the sem, or let the bot administrator know if they do so.** The format of the file is as follows:

```
{
    "staff": [  # Telegram usernames of reflection tutors
        "john",
        "doe",
        ...
    ],
    "admin": [  # Telegram usernames of module/bot administrators
        "jane",
        "doe",
        ...
    ]
}
```

## Update sheet and credentials file string in `main.py`

Once the credentials have been downloaded from Google and the Google Sheets file is set up, you can change the `SHEET` and `CREDENTIALS` variable in `main.py` so the bot knows which access credentials to use and which attendance sheet to work with.

## Deploy the bot

### Setup directory and Python libraries in a Linux server

You can deploy the Telegram bot if you have access to a Linux server. Just clone the repository, [setup a Python virtual environment inside the repository folder](https://docs.python.org/3/library/venv.html), and activate the virtual environment. After that, you can run the command `pip install -r requirements.txt` to install the relevant Python libraries.

### Install Redis

We use Redis for storing our persistent data, such as mappings between Telegram user ID and relevant sheet row for the student. **It is for this reason that the sheet rows should not be messed up. If you want to add new student IDs once other students have started registering themselves on the bot, please add it at the end of the sheet.** Ensure that [Redis is installed](https://redis.io/docs/getting-started/installation/install-redis-on-linux/) in the server.

### Update the bot key inside `main.py`

The attendance bot is identified using a unique key on Telegram. In the `main()` function, `os.environ.get('TELEKEY')` gets this unique key. Set the environment variable for `TELEKEY` to finish deployment.

### Run the bot as a Linux service

Once the bot libraries are installed, [you can run the bot script as a Linux service](https://medium.com/codex/setup-a-python-script-as-a-service-through-systemctl-systemd-f0cc55a42267). This ensures that exiting the server does not stop the Telegram bot, which is essentially a continuously running Python script.

## Run tests

We do not have any unit tests setup for the bot yet. However, to test, you can add sample student IDs in the attendance sheet. Bot admins can register using that sample student ID, create an attendance session and also mark their own attendance to check if everything works correctly.
