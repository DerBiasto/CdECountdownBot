import logging
import sqlite3
import datetime

logger = logging.getLogger(__name__)

class Akademie:
    def __init__(self, name, description="", date=""):
        self.name = name
        self.description = description
        try:
            date = date.strip()
            self.date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            self.date = None


class DBHelper:
    def __init__(self, dbname="akademien.sqlite"):
        self.dbname = dbname
        self.c = sqlite3.connect(dbname)

    def setup(self):
        q = "CREATE TABLE IF NOT EXISTS akademien(name text, description text, date text)"
        self.c.execute(q)
        q = "CREATE INDEX IF NOT EXISTS akademieName ON akademien (name ASC)"
        self.c.execute(q)
        q = "CREATE TABLE IF NOT EXISTS chats (chatID text, lastMessage text)"
        self.c.execute(q)
        q = "CREATE TABLE IF NOT EXISTS subscribers (chatID text, subscriptions text, time text)"
        self.c.execute(q)
        self.c.commit()

    def add_akademie(self, name, description="", date=""):
        q = "INSERT INTO akademien (name, description, date) VALUES (?, ?, ?)"
        args = (name, description, date)
        self.c.execute(q, args)
        self.c.commit()
        logger.info("Created new academy '{}' at {}".format(name, date))

    def delete_akademie(self, name):
        q = "DELETE FROM akademien WHERE name = (?)"
        args = (name,)
        self.c.execute(q, args)
        self.c.commit()
        logger.info("Deleted academy '{}'".format(name))

    def edit_akademie(self, name, new_name, new_description, new_date):
        if not self.c.execute("SELECT * FROM akademien WHERE name = ?", (name, )).fetchone(): 
            print('Keine Akademie unter diesem Namen gefunden.')
            return
        if new_date != '':
            q = "UPDATE akademien SET date = ? WHERE name = ?"
            args = (new_date, name)
            self.c.execute(q, args)
        if new_description != '':
            q = "UPDATE akademien SET description = ? WHERE name = ?"
            args = (new_description, name)
            self.c.execute(q, args)
        if new_name != '':
            q = "UPDATE akademien SET name = ? WHERE name = ?"
            args = (new_name, name)
            self.c.execute(q, args)
        self.c.commit()
        logger.info("Edited academy '{}'".format(name))

    def get_akademien(self):
        q = "SELECT name, description, date FROM akademien"
        result = []
        for row in self.c.execute(q):
            result.append(Akademie(row[0], row[1], row[2]))
        return result

    def get_last_message_time(self, chat_id):
        q = "SELECT lastMessage FROM chats WHERE chatID = ?"
        args = (chat_id,)
        result = [x[0] for x in self.c.execute(q, args)]

        return result

    def set_last_message_time(self, chat_id):
        if not self.get_last_message_time(chat_id):
            q = "INSERT INTO chats (lastMessage, chatID) VALUES (?, ?)"
        else:
            q = "UPDATE chats SET lastMessage = ? WHERE chatID = ?"
        args = (datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f'), chat_id)
        self.c.execute(q, args)
        self.c.commit()

    def add_subcription(self, chat_id, subscriptions, time='06:00:00'):
        
        if not self.c.execute("SELECT subscriptions FROM subscribers WHERE chatID = ? AND time = ?",
                              (chat_id, time))\
                .fetchone():
            q = "INSERT INTO subscribers (chatID, subscriptions, time) VALUES (?, ?, ?)"
            args = (chat_id, subscriptions, time)
            self.c.execute(q, args)
            self.c.commit()
            logger.info("Added subscription for {} at {}".format(chat_id, time))
        else:
            logger.warning("Chat {} has already a subscription for {}".format(chat_id, time))

    def remove_subscription(self, chat_id, time=None):
        if time:
            q = "DELETE FROM subscribers WHERE chatID = ? and time = ?"
            args = (chat_id, time)
        else:
            q = "DELETE FROM subscribers WHERE chatID = ?"
            args = (chat_id,)
        self.c.execute(q, args)
        self.c.commit()
        logger.info("Removed subscriptions of {}{}".format(chat_id, " at {}".format(time) if time else ""))

    def get_subscriptions(self, subscriptions):
        q = "SELECT chatID, time FROM subscribers WHERE subscriptions = ?"
        args = (subscriptions,)
        return [s for s in self.c.execute(q, args)]
