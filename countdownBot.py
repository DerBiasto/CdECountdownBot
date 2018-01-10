#!/usr/bin/env python3
import requests
import json
import time
import datetime
from datetime import timedelta
import urllib
from dbhelper import DBHelper

TOKEN = "515125129:AAEcTqebHq2uhJaCDMssglu_98Len6FpbGY"
URL = "https://api.telegram.org/bot{}/".format(TOKEN)

db = DBHelper()

def getURL(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content
    
def getJsonFromURL(url):
    content = getURL(url)
    js = json.loads(content)
    return js
    
def getUpdates(offset=None,timeout=10):
    url = URL + "getUpdates?timeout={}".format(timeout)
    if offset:
        url += "&offset={}".format(offset)
    #print(url)
    js = getJsonFromURL(url)
    return js
    
    
def getLastUpdateID(updates):
    updateIDs = []
    for update in updates["result"]:
        updateIDs.append(update["update_id"])
    return max(updateIDs)
    
def sendMessage(text, chatID, replyMarkup=None, parseMode=None):
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chatID)
    if replyMarkup:
        url += "&reply_markup={}".format(replyMarkup)
    if parseMode:
        url += "&parse_mode={}".format(parseMode)
    getURL(url)

def editMessageText(text, chatID, messageID, replyMarkup=None):
    text = urllib.parse.quote_plus(text)
    url = URL + "editMessageText?text={}&chat_id={}&message_id={}".format(text, chatID, messageID)
    if replyMarkup:
        url += "&reply_markup={}".format(replyMarkup)
    getURL(url)
    
def echoAll(updates):
    for update in updates["result"]:
        try:
            text = update["message"]["text"]
            chatID = update["message"]["chat"]["id"]
            sendMessage(text, chatID)
        except Exception as e:
            print(e)

def printAkademien(akademien, chatID=None):
    msgParts = []
    
    charcount = 0
    
    for a in (a for a in akademien):
        if a.date:
            msg ='{} -- {}'.format(a.name, a.date.strftime('%d.%m.%Y'))
            msgParts.append(msg)
            msg ='\t-- _{}_\n'.format(a.description)
            msgParts.append(msg)
        else:
            msgParts.append('{}\n\t-- _{}_\n'.format(a.name, a.description))
        
    if chatID:
        sendMessage("\n".join(msgParts), chatID, parseMode="Markdown")
        
    return msgParts
    
def printAkademieCountdown(akademien, chatID=None, preText=None, postText=None):
    akaList = []
    
    for a in (a for a in sorted(akademien, key=lambda a: (a.date))):
        akaList.append('Es sind noch {} Tage bis zur {}\n\t-- _{}_\n'.format((a.date - datetime.datetime.today().date()).days, a.name, a.description))
        
    msg = '\n'.join(akaList)
        
    if preText:
        msg = preText + msg
    
    if postText:
        msg = msg + postText
        
    if chatID:
        sendMessage(msg, chatID, parseMode="Markdown")
        
    return msg
    
def tooMuchSpam(update):
    
    if update["message"]["chat"]["type"] == "private":
        return False
    elif update["message"]["chat"]["type"] == "group" or update["message"]["chat"]["type"] == "supergroup":
        lastMsg = db.getLastMessageTime(update["message"]["chat"]["id"])
        if lastMsg == []:
            db.setLastMessageTime(update["message"]["chat"]["id"])
            return False
        else:
            delta = datetime.datetime.now() - datetime.datetime.strptime(lastMsg[0], '%Y-%m-%d %H:%M:%S.%f')
            if delta < timedelta(minutes=5):
                print("Too much spam in chat {}".format(update["message"]["chat"]["id"]))
                return True
            db.setLastMessageTime(update["message"]["chat"]["id"])
            return False
        
        return False    

def handleUpdates(updates):
    for update in updates["result"]:
        if "message" in update.keys():
            try:
                msg = update["message"]
                text = msg["text"]
                chatID = msg["chat"]["id"]
                akademien = db.getAkademien()
                
                args = text.split(' ', 1)
                
                command = args[0].replace('@cde_akademie_countdown_bot','')
                
                if command.startswith('/'):
                    if command == '/start':
                        sendMessage('Hallo! Ich bin ein Bot um die Tage bis zur nächsten CdE Akademie zu zählen!', chatID)
                    elif command == '/list' and not tooMuchSpam(update):
                        if len(akademien) > 0:
                            printAkademien(akademien, chatID)
                        else:
                            sendMessage('Es sind noch keine Akademien eingespeichert :\'(', chatID)
                    elif command == '/countdown' and not tooMuchSpam(update):
                        akaCountdown = [a for a in akademien if a.date]
                        
                        if len(args) > 1:
                            name = args[1].strip()
                            akaCountdown = [a for a in akaCountdown if a.name == name]
                            if len(akaCountdown) == 0:
                                sendMessage('Es ist keine Akademie mit diesem Namen bekannt, oder diese Akademie hat kein Startdatum', chatID)
                                continue
                        if len(akaCountdown) > 0:
                            printAkademieCountdown(akaCountdown, chatID)
                        else:
                            sendMessage('Es sind noch keine Akademien mit Datum eingespeichert :\'(', chatID)
                    elif command == '/subscribe':
                        if len(args) > 1:
                            try:
                                time = datetime.datetime.strptime(args[1], '%H:%M').strftime('%H:%M')
                                db.addSubcription(chatID, '1', time)
                                sendMessage('Countdownbenachrichtigungen für täglich {} Uhr(UTC) erfolgreich abonniert!'.format(time), chatID)
                            except ValueError:
                                db.addSubcription(chatID, '1')
                                sendMessage('Uhrzeit konnte nicht gelesen werden. Tägliche Benachrichtigungen wurden für 06:00 Uhr(UTC) abonniert!', chatID)
                        else:
                            db.addSubcription(chatID, '1')
                            sendMessage('Tägliche Benachrichtigungen für 06:00 Uhr(UTC) erfolgreich abonniert!', chatID)
                            
                        
                    elif command == '/unsubscribe':
                        db.removeSubscription(chatID)
                        sendMessage('Alle täglichen Benachrichtigungen für diesen Chat wurden erfolgreich gelöscht!', chatID)
                    elif command == '/now':
                        sendMessage(datetime.datetime.utcnow().strftime('%H:%M:%S'), chatID)
                    elif msg["from"]["id"] != 459053986:
                        sendMessage('Du hast leider nicht die erforderliche Berechtigung um diesen Befehl auszuführen :/', chatID)
                        continue
                    elif command == '/add_akademie':
                        if len(args) <= 1:
                            sendMessage('Bitte gib einen Namen für die neue Akademie ein. Du kannst außerdem eine Beschreibung und ein Startdatum angeben.\nDie Syntax lautet: Name;Beschreibung;Datum(YYYY-MM-DD)', chatID)
                        else:
                            try:
                                name, description, date = args[1].split(';',2)
                            except ValueError:
                                try: 
                                    name, description = args[1].split(';',1)
                                    date = ''
                                except ValueError:
                                    name = args[1]
                                    description = ''
                                    date = ''
                                    
                            name = name.strip()
                            description = description.strip()
                            date = date.strip()
                            for a in akademien:
                                if a.name == name:
                                    sendMessage('Es existiert bereits eine Akademie mit diesem Namen!', chatID)
                                    break
                            else:
                                db.addAkademie(name, description, date)
                                sendMessage('Akademie {} hinzugefügt'.format(name), chatID)
                                akademien = db.getAkademien()
                        printAkademien(akademien, chatID)
                    elif command == '/delete_akademie':
                        keyboard = buildInlineKeyboard(akademien)
                        sendMessage('Wähle eine Akademie aus die gelöscht werden soll', chatID, keyboard)
                    elif command == '/edit_akademie':
                        if len(args) <= 1:
                            sendMessage('Bitte gib an, welche Akademie du ändern willst. \nDie Syntax lautet: /change_akademie Name; Neuer Name; Neue Beschreibung; Neues Datum. Leere Angaben bleiben unverändert.', chatID)
                        else:
                            try:
                                name, newName, newDescription, newDate = args[1].split(';', 3)
                                name = name.strip()
                                newName = newName.strip()
                                newDescription = newDescription.strip()
                                newDate = newDate.strip()
                            except:
                                sendMessage('Beim Einlesen deiner Änderung ist ein Fehler aufgetreten :(\nWahrscheinlich hast du zu wenige Argumente angegeben.', chatID)
                            else:
                                db.editAkademie(name, newName, newDescription, newDate)
                                akademien = db.getAkademien()
                                printAkademien(akademien, chatID)
                    elif command == '/send_subscriptions':
                        sendSubscriptions('1', force=True)
                    elif command == '/get_subscriptions':
                        print(db.getSubscriptions('1'))
                        
                                
                        
            except KeyError:
                pass
                
        elif "callback_query" in update.keys():
            try:
                cq = update["callback_query"]
                
                text = cq["data"]
                
                args = text.split(' ', 1)
                
                command = args[0].replace('@cde_akademie_countdown_bot', '')
                
                if len(args) > 1:
                    if cq["from"]["id"] != 459053986:
                        editMessageText('Du hast leider nicht die erforderlichen Berechtigung um diesen Befehl auszuführen :/'.format(args[1]), cq["message"]["chat"]["id"], cq["message"]["message_id"])
                        continue
                    elif command == '/delete_akademie':
                        #print(args[1])
                        db.deleteAkademie(args[1])
                        editMessageText('Akademie {} wurde gelöscht'.format(args[1]), cq["message"]["chat"]["id"], cq["message"]["message_id"])
                
            except KeyError as e:
                print('KeyError: {}'.format(e))
                pass
                
            
def buildInlineKeyboard(akademien):
    keyboard = [[{"text": a.name, "callback_data": '/delete_akademie {}'.format(a.name)}] for a in akademien]
    replyMarkup = {"inline_keyboard": keyboard}
    return json.dumps(replyMarkup)

def sendSubscriptions(subscription, force=False):
    
    #print("sending Subscriptions")
    
    subscribers = db.getSubscriptions(subscription)
    now = datetime.datetime.utcnow().strftime('%H:%M')
    
    akademien = db.getAkademien()
    akaCountdown = [a for a in akademien if a.date]
    
    for s in subscribers:
        #print(s)
        if s[1] == now or force:
            #print('Send to this Subscriber')
            printAkademieCountdown(akaCountdown, s[0], preText = 'Dies ist deine für {} Uhr(UTC) abonnierte Nachricht:\n\n'.format(now))
        
    return
    
def main():
    db.setup()
    lastUpdateID = None
    now = datetime.datetime.now().strftime('%H:%M')
    while True:
        updates = getUpdates(lastUpdateID)
        if len(updates["result"]) > 0:
            lastUpdateID = getLastUpdateID(updates) + 1
            handleUpdates(updates)
        if now != datetime.datetime.now().strftime('%Y-%m-%d %H:%M'):
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            sendSubscriptions('1')
        time.sleep(0.5)
        
if __name__ == "__main__":
    main()
