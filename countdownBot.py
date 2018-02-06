#!/usr/bin/env python3
import requests
import json
import time
import datetime
from datetime import timedelta
import urllib.parse
from dbhelper import DBHelper
import configparser

db = DBHelper()


class TClient:
    URL = "https://api.telegram.org/bot{}/{}"

    def __init__(self, token):
        self.token = token

    def _get_telegram_url(self, url):
        response = requests.get(self.URL.format(self.token, url))
        content = response.content.decode("utf8")
        return content

    def get_json_from_url(self, url):
        content = self._get_telegram_url(url)
        js = json.loads(content)
        return js

    def get_updates(self, offset=None, timeout=10):
        url = "getUpdates?timeout={}".format(timeout)
        if offset:
            url += "&offset={}".format(offset)
        # print(url)
        js = self.get_json_from_url(url)
        return js

    def send_message(self, text, chat_id, reply_markup=None, parse_mode=None):
        text = urllib.parse.quote_plus(text)
        url = "sendMessage?text={}&chat_id={}".format(text, chat_id)
        if reply_markup:
            url += "&reply_markup={}".format(reply_markup)
        if parse_mode:
            url += "&parse_mode={}".format(parse_mode)
        self._get_telegram_url(url)

    def edit_message_text(self, text, chat_id, message_id, reply_markup=None):
        text = urllib.parse.quote_plus(text)
        url = "editMessageText?text={}&chat_id={}&message_id={}".format(text, chat_id, message_id)
        if reply_markup:
            url += "&reply_markup={}".format(reply_markup)
        self._get_telegram_url(url)

    def echo_all(self, updates):
        for update in updates["result"]:
            try:
                text = update["message"]["text"]
                chat_id = update["message"]["chat"]["id"]
                self.send_message(text, chat_id)
            except Exception as e:
                print(e)


def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(update["update_id"])
    return max(update_ids)


def print_akademien(tclient, akademien, chat_id=None):
    msg_parts = []

    for a in (a for a in sorted(akademien, key=lambda x: x.name)):
        if a.date:
            msg = '{} -- {}'.format(a.name, a.date.strftime('%d.%m.%Y'))
            msg_parts.append(msg)
            msg = '\t-- _{}_\n'.format(a.description)
            msg_parts.append(msg)
        else:
            msg_parts.append('{}\n\t-- _{}_\n'.format(a.name, a.description))

    if chat_id:
        tclient.send_message("\n".join(msg_parts), chat_id, parse_mode="Markdown")

    return msg_parts


def print_akademie_countdown(tclient, akademien, chat_id=None, pre_text=None, post_text=None):
    aka_list = []

    for a in (a for a in sorted(akademien, key=lambda x: x.date)):
        if a.name.endswith('kademie') or a.name.endswith('Aka'):
            aka_list.append(
                'Es sind noch {} Tage bis zur {}\n\t-- _{}_\n'.format((a.date - datetime.datetime.today().date()).days,
                                                                      a.name, a.description))
        elif a.name == 'Seminar' or a.name.endswith('Segeln'):
            aka_list.append(
                'Es sind noch {} Tage bis zum {}\n\t-- _{}_\n'.format((a.date - datetime.datetime.today().date()).days,
                                                                      a.name, a.description))
        else:
            aka_list.append('Es sind noch {} bis zur Veranstaltung {}\n\t-- _{}_\n'.format(
                (a.date - datetime.datetime.today().date()).days, a.name, a.description))

    msg = '\n'.join(aka_list)

    if pre_text:
        msg = pre_text + msg

    if post_text:
        msg = msg + post_text

    if chat_id:
        tclient.send_message(msg, chat_id, parse_mode="Markdown")

    return msg


def too_much_spam(update):
    if update["message"]["chat"]["type"] == "private":
        return False
    elif update["message"]["chat"]["type"] == "group" or update["message"]["chat"]["type"] == "supergroup":
        last_msg = db.get_last_message_time(update["message"]["chat"]["id"])
        if not last_msg:
            db.set_last_message_time(update["message"]["chat"]["id"])
            return False
        else:
            delta = datetime.datetime.utcnow() - datetime.datetime.strptime(last_msg[0], '%Y-%m-%d %H:%M:%S.%f')
            if delta < timedelta(minutes=5):
                print("Too much spam in chat {}".format(update["message"]["chat"]["id"]))
                return True
            db.set_last_message_time(update["message"]["chat"]["id"])
            return False


def handle_updates(updates, tclient):
    for update in updates["result"]:
        if "message" in update.keys():
            try:
                msg = update["message"]
                text = msg["text"]
                chat_id = msg["chat"]["id"]
                akademien = db.get_akademien()

                args = text.split(' ', 1)

                command = args[0].replace('@cde_akademie_countdown_bot', '')

                if command.startswith('/'):
                    if command == '/start':
                        tclient.send_message(
                            'Hallo! Ich bin ein Bot, um die Tage bis zur nächsten CdE Akademie zu zählen!', chat_id)
                    elif command == '/list':
                        if too_much_spam(update):
                            continue
                        if len(akademien) > 0:
                            print_akademien(tclient, akademien, chat_id)
                        else:
                            tclient.send_message('Es sind noch keine Akademien eingespeichert :\'(', chat_id)
                    elif command == '/countdown':
                        if too_much_spam(update):
                            continue
                        aka_countdown = [a for a in akademien if a.date]

                        if len(args) > 1:
                            name = args[1].strip()
                            aka_countdown = [a for a in aka_countdown if a.name == name]
                            if len(aka_countdown) == 0:
                                tclient.send_message(
                                    'Es ist keine Akademie mit diesem Namen bekannt, oder diese Akademie hat '
                                    'kein Startdatum',
                                    chat_id)
                                continue
                        if len(aka_countdown) > 0:
                            print_akademie_countdown(tclient, aka_countdown, chat_id)
                        else:
                            tclient.send_message('Es sind noch keine Akademien mit Datum eingespeichert :\'(', chat_id)
                    elif command == '/subscribe':
                        if len(args) > 1:
                            try:
                                t = datetime.datetime.strptime(args[1], '%H:%M').strftime('%H:%M')
                                db.add_subcription(chat_id, '1', t)
                                tclient.send_message(
                                    'Countdownbenachrichtigungen für täglich {} Uhr(UTC) erfolgreich abonniert!'
                                    .format(t), chat_id)
                            except ValueError:
                                db.add_subcription(chat_id, '1')
                                tclient.send_message(
                                    'Uhrzeit konnte nicht gelesen werden. Tägliche Benachrichtigungen wurden für '
                                    '06:00 Uhr(UTC) abonniert!',
                                    chat_id)
                        else:
                            db.add_subcription(chat_id, '1')
                            tclient.send_message('Tägliche Benachrichtigungen für 06:00 Uhr(UTC)'
                                                 'erfolgreich abonniert!',
                                                 chat_id)
                    elif command == '/unsubscribe':
                        db.remove_subscription(chat_id)
                        tclient.send_message(
                            'Alle täglichen Benachrichtigungen für diesen Chat wurden erfolgreich gelöscht!', chat_id)
                    elif command == '/now':
                        tclient.send_message(datetime.datetime.utcnow().strftime('%H:%M:%S'), chat_id)
                    elif msg["from"]["id"] != 459053986:
                        tclient.send_message(
                            'Du hast leider nicht die erforderliche Berechtigung um diesen Befehl auszuführen :/',
                            chat_id)
                        continue
                    elif command == '/add_akademie':
                        if len(args) <= 1:
                            tclient.send_message(
                                'Bitte gib einen Namen für die neue Akademie ein. Du kannst außerdem eine Beschreibung '
                                'und ein Startdatum angeben.\nDie Syntax lautet: Name;Beschreibung;Datum(YYYY-MM-DD)',
                                chat_id)
                        else:
                            try:
                                name, description, date = args[1].split(';', 2)
                            except ValueError:
                                try:
                                    name, description = args[1].split(';', 1)
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
                                    tclient.send_message('Es existiert bereits eine Akademie mit diesem Namen!',
                                                         chat_id)
                                    break
                            else:
                                db.add_akademie(name, description, date)
                                tclient.send_message('Akademie {} hinzugefügt'.format(name), chat_id)
                                akademien = db.get_akademien()
                        print_akademien(tclient, akademien, chat_id)
                    elif command == '/delete_akademie':
                        keyboard = build_inline_keyboard(akademien)
                        tclient.send_message('Wähle eine Akademie aus die gelöscht werden soll', chat_id, keyboard)
                    elif command == '/edit_akademie':
                        if len(args) <= 1:
                            tclient.send_message(
                                'Bitte gib an, welche Akademie du ändern willst.\n'
                                'Die Syntax lautet: /change_akademie Name; Neuer Name; Neue Beschreibung; Neues Datum. '
                                'Leere Angaben bleiben unverändert.',
                                chat_id)
                        else:
                            try:
                                name, new_name, new_description, new_date = args[1].split(';', 3)
                                name = name.strip()
                                new_name = new_name.strip()
                                new_description = new_description.strip()
                                new_date = new_date.strip()
                            except:
                                tclient.send_message(
                                    'Beim Einlesen deiner Änderung ist ein Fehler aufgetreten :(\n'
                                    'Wahrscheinlich hast du zu wenige Argumente angegeben.',
                                    chat_id)
                            else:
                                db.edit_akademie(name, new_name, new_description, new_date)
                                akademien = db.get_akademien()
                                print_akademien(tclient, akademien, chat_id)
                    elif command == '/send_subscriptions':
                        send_subscriptions(tclient, '1', force=True)
                    elif command == '/get_subscriptions':
                        print(db.get_subscriptions('1'))
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
                        tclient.edit_message_text(
                            'Du hast leider nicht die erforderlichen Berechtigung um diesen Befehl auszuführen :/'
                            .format(args[1]), cq["message"]["chat"]["id"], cq["message"]["message_id"])
                        continue
                    elif command == '/delete_akademie':
                        # print(args[1])
                        db.delete_akademie(args[1])
                        tclient.edit_message_text('Akademie {} wurde gelöscht'.format(args[1]),
                                                  cq["message"]["chat"]["id"], cq["message"]["message_id"])

            except KeyError as e:
                print('KeyError: {}'.format(e))
                pass


def build_inline_keyboard(akademien):
    keyboard = [[{"text": a.name, "callback_data": '/delete_akademie {}'.format(a.name)}] for a in akademien]
    reply_markup = {"inline_keyboard": keyboard}
    return json.dumps(reply_markup)


def send_subscriptions(tclient, subscription, force=False):
    # print("sending Subscriptions")

    subscribers = db.get_subscriptions(subscription)
    now = datetime.datetime.utcnow().strftime('%H:%M')

    akademien = db.get_akademien()
    aka_countdown = [a for a in akademien if a.date]

    for s in subscribers:
        # print(s)
        if s[1] == now or force:
            # print('Send to this Subscriber')
            print_akademie_countdown(tclient, aka_countdown, s[0],
                                     pre_text='Dies ist deine für {} Uhr(UTC) abonnierte Nachricht:\n\n'.format(now))

    return


def main():
    # Setup DB
    db.setup()

    # Read configuration and setup Telegram client
    config = configparser.ConfigParser()
    config.read('config.ini')
    tclient = TClient(config['telegram']['token'])

    last_update_id = None
    now = datetime.datetime.utcnow().strftime('%H:%M')
    while True:
        updates = tclient.get_updates(last_update_id)
        try:
            if len(updates["result"]) > 0:
                last_update_id = get_last_update_id(updates) + 1
                handle_updates(updates, tclient)
            if now != datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M'):
                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')
                send_subscriptions(tclient, '1')
            time.sleep(0.5)
        except KeyError:
            pass


if __name__ == "__main__":
    main()
