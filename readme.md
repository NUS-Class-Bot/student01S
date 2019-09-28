# NUS Class Bot - NUS CP3108B Project

Project Supervisor: A/P [Martin Henz](https://github.com/martin-henz)

Advisor: [Tobias Wrigstad](https://github.com/TobiasWrigstad)

Current Student Developers: [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah) 

Co-Founders: [Advay Pal](https://github.com/advaypal), [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah) 

## The Problem

Currently, the attendance taking process in NUS is the same old concept from the 1980s: either pass a sheet around for sign or do a roll-call of names. However, both these problems are prone to cheating by students as it is to be a *proxy* for someone. Furthermore, it is also a hassle for instructors to *transfer* the data from a physical sheet to a computer based record for further marking. Both the above methods also consume about 5 minutes of precious class time for each tutorial session. 

Since at the School of Computing, attendance taking and participation in tutorial comprise of a significant part of learning and assessment, we thought of building a cool solution to this problem. 

## The Solution 

NUS Class Bot is a [Telegram](https://telegram.org/) Bot to solve the above mentioned problem. The bot stores the attendance data collected in real-time on a Google Spreadsheet, pre-setup during deployment that is shared with module staff.

The bot on this repository has been specifically designed for use with [CS1101S](https://comp.nus.edu.sg/~cs1101s/), an expertial introductory programming module for CS Freshman at NUS-SoC. Here's a basic work-flow:

1. `Tutor` counts number of student present in the class. 
2. `Tutor` starts taking attendance using `/start_session` (num of students). 
2. `Bot` gives the `Tutor` a `Token` of 8 digits.
3. `Tutor` shares the `Token` with the students present in the classroom by writing it on a white board.
4. `Students` mark attendance using `/attend` (`Token`). If the classroom is already *full* (number of students indicated in step 2 is reached), or if the `Token` is incorrect, the attendance is not marked and the `Student` is informed of the same. If there's a problem, the `Student` can approach the `Tutor`, who can immediately check on the `Google Sheet`.
5. `Tutor` finishes the process by sending `/stop_session` to the bot.

Here's a comprehensive summary of all the command supported by the bot and their function:

| Command                        | For user           | Function |
| -------------                  |-------------| -----|
| `/setup <student number>`      | `Student`          |  To setup with the bot's database (onetime process)  |
| `/attend <token>`               |   `Student`        |  To mark attendance  |
| `/attendance_reflection`        | `Student`           | To check attendance data for reflection sessions till date.  |
| `/attendance_studio`        | `Student`           | To check attendance data for studio sessions (tutorials) till date.  |
| `/start_session <num students>`        | `Tutor`           | To mark the attendance for `num students` for 1 class  |
| `/stop_session`        | `Tutor`           | To stop taking attendance for current session.  |
| `/comment`        | `Tutor`           | To trigger a set of commands to give feedback on a student's performance in a particular session.  |
| `/comment`        | `Tutor`           | To trigger a set of commands to give feedback on a student's performance in a particular session.  |



The bot is currently used by the staff of CS1101S for tutorials, reflection sessions and staff meetings. Thus, the bot currently has approximately 600 active users. 
 
## Development Process 


## Problems & Solutions

