# NUS Class Bot - NUS CP3108B Project

Project Supervisor: A/P [Martin Henz](https://github.com/martin-henz)

Advisor: [Tobias Wrigstad](https://github.com/TobiasWrigstad)

Current Student Developers: [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah) 

Co-Founders: [Advay Pal](https://github.com/advaypal), [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah) 

## The Problem

Currently, the attendance taking process in NUS is the same old concept from the 1980s: either pass a sheet around for sign or do a roll-call of names. However, both these problems are prone to cheating by students as it is easy to be a *proxy* for someone. Furthermore, it is also a hassle for instructors to *transfer* the data from a physical sheet to a computer based record for further marking. Both the above methods also consume about 5 minutes of precious class time for each tutorial session. Usually, an NUS class has 10 tutorials per semester and this leads to a waste of 5 x 10 = 50 minutes each semester of students and teaching assistants. 

Since attendance and participation are important for learning and assessment at SoC, we thought of building a cool solution to this problem. 

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

The development process for the bot can effectively be divided into the following phases: ideation, prototyping, testing and final development. Ideation consisted of formulating the system design for the bot, following which a minimum viable product (prototype) was developed. The prototype was tested in some tutorials before using it over a wide scale. The success of the bot in those particular tutorial classes motivated us to scale it up, which consisted of developing a Telegram Bot
designed especially for the module CS1101S.

1. **Ideation Phase:** This phase involved formulating the design of our bot, ranging from the workflow to the way it addresses the automation of attendance taking (without allowing students absent from the tutorial to mark their attendance). Some of the design decisions characteristic of the bot included generating a hash token based on the timestamp of the computer, and limiting the usage of the hash token by counting the number of students present. Since hash tokens differ significantly even with minor changes in the input, we can be reaonsably sure that tokens generated are not the same at any point of time. The second important design decision was passing the number along with the command `start_session`. This serves as a quick way to ensure that students do not pass the token outside of class, since if someone outside the class marks an attendance, someone inside will not be able to do so. We have mainly not had cases of attendance token being passed outside, so this solution seems to be working fine.

2. **Prototyping Phase:** The next phase involved actually creating the bot. To create the bot, we chose the API `python-telegram-bot` for its ease of use (and our familiarity with Python). For data storage, we chose Redis over other services like SQL databases because all our data is effectively stored using dictionaries, and Redis seems to be a lightweight and popular choice for persistent storage of key-value dictionaries. To develop a minimum viable product, we hardcoded the Tutor Telegram usernames and Google Sheet ID simply to get the bot up and running. The priority during this phase was to implement core functionalities like integration with Google Sheets and setting up the bot workflow.

3. **Testing Phase:** After setting up the basic skeleton for the bot, we decided to test it unofficially during some tutorials. This was mainly to gain user feedback, understand the various test cases and discover unnoticed bugs. Advay tested the bot during his tutorial, and we also conducted "mock" tutorial sessions at our residential college. We discovered important bugs during this phase, such as the absence of a Telegram useraname for the student and also workflow errors. The testing phase greatly helped us in making the bot more polished and user-friendly.

4. **Final development and scaling up the solution:** The final phase of implementing the bot involved making changes to the bot to adhere to CS1101S's needs and workflows, as well as onboarding the huge freshman/tutor base onto the bot. Changes involved dedicating the bot to populate only certain spreadsheets, reading tutor data from JSON files, as well as deciding which week to populate attendance for based on a JSON file which charts out the different weeks in the academic year. The `comment` feature was included in the bot as a liast minute addition, so tutors of CS1101S can comment their students on the Studio sessions. The `feedback` method to garner user feedback for the bot was also implemented during this phase. This phase is still ongoing, and we provide constant support to the tutors/students who face problems using the bot.

## Problems & Solutions

