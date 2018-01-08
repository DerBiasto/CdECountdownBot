import sqlite3
import datetime

class Akademie:
    def __init__(self, name, description="", date=""):
        self.name = name
        self.description = description
        try:
            date = date.strip()
            self.date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except:
            self.date = None

class DBHelper:
    def __init__(self, dbname="akademien.sqlite"):
        self.dbname = dbname
        self.c = sqlite3.connect(dbname)
        
    def setup(self):
        q = "CREATE TABLE IF NOT EXISTS akademien(name text, description text, date text)"
        self.c.execute(q)
        q = "CREATE INDEX IF NOT EXISTS akademieName ON akademien (name ASC)"
        self.c.commit()
        
    def addAkademie(self, name, description="", date=""):
        q = "INSERT INTO akademien (name, description, date) VALUES (?, ?, ?)"
        args = (name, description, date)
        self.c.execute(q, args)
        self.c.commit()
        
    def deleteAkademie(self, name):
        q = "DELETE FROM akademien WHERE name = (?)"
        args = (name, )
        self.c.execute(q, args)
        self.c.commit()
        
    def updateAkademie(self, name, newName, newDescription, newDate):
        if newDate != '':
            q = "UPDATE akademien SET date = ? WHERE name = ?"
            args = (newDate, name)
            self.c.execute(q, args)
        if newDescription != '':
            q = "UPDATE akademien SET description = ? WHERE name = ?"
            args = (newDescription, name)
            self.c.execute(q, args)
        if newName != '':
            q = "UPDATE akademien SET name = ? WHERE name = ?"
            args = (newName, name)
            self.c.execute(q, args)
        self.c.commit()
       
    def getAkademien(self):
        q = "SELECT name, description, date FROM akademien"
        result = []
        for row in self.c.execute(q):
            result.append(Akademie(row[0],row[1],row[2]))
        return result
        
        
