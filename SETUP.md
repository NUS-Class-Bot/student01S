# NUS Class Bot - Setup Guide

Project Supervisor: A/P [Martin Henz](https://github.com/martin-henz). Project Advisor: [Tobias Wrigstad](https://github.com/TobiasWrigstad)

Student Developers: [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah). Co-Founders: [Advay Pal](https://github.com/advaypal), [Chaitanya Baranwal](https://github.com/chaitanyabaranwal) and [Raivat Shah](https://github.com/raivatshah)

This guide is for bot administrators to setup and deploy the bot from scratch, so it can continue making attendance simpler in the future!

## Setting up a Google Sheet for Attendance

1. Mention template.
2. Mention how to create Sheet.

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

Currently the Telegram usernames which are assigned as reflection tutors and bot administrators are hardcoded in the `records/people.json` file. Only usernames mentioned in this file can access the tutor functions of the but (such as starting and stopping attendance sessions). **It is for this reason that tutors should not change their Telegram usernames throughout the sem, or let the bot administrator know if they do so.**

## Update sheet name and credentials file

## Deploy the bot

## Run tests
