#!/usr/bin/env python3
import requests
import json
import time
import datetime
from datetime import timedelta
import urllib.parse
from dbhelper import DBHelper
import configparser


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


class CountdownBot:
    def __init__(self, db, tclient):
        """
        Initialize a CountdownBot object using the given database connector and telegram client object
        :param db: A DBHelper to connect to the SQLite database
        :type db: DBHelper
        :param tclient: A TClient to send messages to the Telegram API
        :type tclient: TClient
        """
        self.db = db
        self.tclient = tclient

    def send_subscriptions(self, subscription, force=False):
        # print("sending Subscriptions")

        subscribers = self.db.get_subscriptions(subscription)
        now = datetime.datetime.utcnow().strftime('%H:%M')

        akademien = self.db.get_akademien()
        aka_countdown = [a for a in akademien if a.date]

        for s in subscribers:
            # print(s)
            if s[1] == now or force:
                # print('Send to this Subscriber')
                self._print_akademie_countdown(
                    aka_countdown, s[0],
                    pre_text='Dies ist deine für {} Uhr(UTC) abonnierte Nachricht:\n\n'.format(now))

    def dispatch_update(self, update):
        """
        Process an update received from the Telegram API in the context of this Bot.
        :param update: A Telegram update to be processed
        :type update: dict
        """
        command_handlers = {
            '/start': self._do_start,
            '/list': self._do_list,
            '/countdown': self._do_countdown,
            '/subscribe': self._do_subscribe,
            '/unsubscribe': self._do_unsubscribe,
            '/now': self._do_now,
            '/add_akademie': self._do_add,
            '/delete_akademie': self._do_delete,
            '/edit_akademie': self._do_edit
        }
        callback_handlers = {
            '/delete_akademie': self._callback_delete
        }

        if "message" in update.keys():
            # Parse command
            args = update["message"]["text"].split(' ', 1)
            command = args[0].replace('@cde_akademie_countdown_bot', '')
            chat_id = update["message"]["chat"]["id"]

            # Call command handler function
            try:
                command_handlers[command](chat_id, args, update)
            except KeyError:
                pass
        elif "callback_query" in update.keys():
            args = update["callback_query"]["data"].split(' ', 1)
            command = args[0].replace('@cde_akademie_countdown_bot', '')
            chat_id = update["callback_query"]["from"]["id"]
            try:
                callback_handlers[command](chat_id, args, update)
            except KeyError:
                pass

    def _do_start(self, chat_id, args, update):
        """
        Handle a /start command. Just send a 'hello' to the user.
        """
        self.tclient.send_message(
            'Hallo! Ich bin ein Bot, um die Tage bis zur nächsten CdE Akademie zu zählen!', chat_id)

    def _do_list(self, chat_id, args, update):
        """
        Handle a /list command. Send a list of all academies to the user
        """
        # Do rate limit for group chat spam protection
        if self._too_much_spam(update):
            return

        akademien = self.db.get_akademien()
        if len(akademien) > 0:
            self._print_akademien(akademien, chat_id)
        else:
            self.tclient.send_message('Es sind noch keine Akademien eingespeichert :\'(', chat_id)

    def _do_countdown(self, chat_id, args, update):
        """
        Handle a /countdown command. Send a list of all academies with remaining number of days to the user.
        """
        # Do rate limit for group chat spam protection
        if self._too_much_spam(update):
            return

        akademien = self.db.get_akademien()
        aka_countdown = [a for a in akademien if a.date]

        if len(args) > 1:
            name = args[1].strip()
            aka_countdown = [a for a in aka_countdown if a.name == name]
            if len(aka_countdown) == 0:
                self.tclient.send_message(
                    'Es ist keine Akademie mit diesem Namen bekannt, oder diese Akademie hat '
                    'kein Startdatum',
                    chat_id)
                return

        if len(aka_countdown) > 0:
            self._print_akademie_countdown(aka_countdown, chat_id)
        else:
            self.tclient.send_message('Es sind noch keine Akademien mit Datum eingespeichert :\'(', chat_id)

    def _do_subscribe(self, chat_id, args, update):
        """
        Handle a /subscribe command.
        """
        if len(args) > 1:
            try:
                t = datetime.datetime.strptime(args[1], '%H:%M').strftime('%H:%M')
                self.db.add_subcription(chat_id, '1', t)
                self.tclient.send_message(
                    'Countdownbenachrichtigungen für täglich {} Uhr(UTC) erfolgreich abonniert!'
                    .format(t), chat_id)
            except ValueError:
                self.db.add_subcription(chat_id, '1')
                self.tclient.send_message(
                    'Uhrzeit konnte nicht gelesen werden. Tägliche Benachrichtigungen wurden für '
                    '06:00 Uhr(UTC) abonniert!',
                    chat_id)
        else:
            self.db.add_subcription(chat_id, '1')
            self.tclient.send_message('Tägliche Benachrichtigungen für 06:00 Uhr(UTC)'
                                      'erfolgreich abonniert!',
                                      chat_id)

    def _do_unsubscribe(self, chat_id, args, update):
        """
        Handle an /unsubscribe command.
        """
        self.db.remove_subscription(chat_id)
        self.tclient.send_message(
            'Alle täglichen Benachrichtigungen für diesen Chat wurden erfolgreich gelöscht!', chat_id)

    def _do_now(self, chat_id, args, update):
        """
        Handle a /now command. Just respond with the current UTC time.
        """
        self.tclient.send_message(datetime.datetime.utcnow().strftime('%H:%M:%S'), chat_id)

    def _do_add(self, chat_id, args, update):
        """
        Handle an /add_akademie command.
        """
        if not self._check_privilege(chat_id):
            self.tclient.send_message(
                'Du hast leider nicht die erforderliche Berechtigung um diesen Befehl auszuführen :/',
                chat_id)
            return

        akademien = self.db.get_akademien()
        if len(args) <= 1:
            self.tclient.send_message(
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
                    self.tclient.send_message('Es existiert bereits eine Akademie mit diesem Namen!',
                                              chat_id)
                    break
            else:
                self.db.add_akademie(name, description, date)
                self.tclient.send_message('Akademie {} hinzugefügt'.format(name), chat_id)
                akademien = self.db.get_akademien()
        self._print_akademien(akademien, chat_id)

    def _do_delete(self, chat_id, args, update):
        """
        Handle an /delete_akademie command.
        """
        if not self._check_privilege(chat_id):
            self.tclient.send_message(
                'Du hast leider nicht die erforderliche Berechtigung um diesen Befehl auszuführen :/',
                chat_id)
            return

        akademien = self.db.get_akademien()
        keyboard = [[{"text": a.name,
                      "callback_data": '/delete_akademie {}'.format(a.name)}]
                    for a in akademien]
        self.tclient.send_message('Wähle eine Akademie aus die gelöscht werden soll', chat_id,
                                  json.dumps({"inline_keyboard": keyboard}))

    def _do_edit(self, chat_id, args, update):
        """
        Handle an /edit_akademie command.
        """
        if not self._check_privilege(chat_id):
            self.tclient.send_message(
                'Du hast leider nicht die erforderliche Berechtigung um diesen Befehl auszuführen :/',
                chat_id)
            return

        if len(args) <= 1:
            self.tclient.send_message(
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
                self.tclient.send_message(
                    'Beim Einlesen deiner Änderung ist ein Fehler aufgetreten :(\n'
                    'Wahrscheinlich hast du zu wenige Argumente angegeben.',
                    chat_id)
            else:
                self.db.edit_akademie(name, new_name, new_description, new_date)
                akademien = self.db.get_akademien()
                self._print_akademien(akademien, chat_id)

    def _do_send_subscriptions(self, chat_id, args, update):
        """
        Handle a /send_subscriptions command.
        """
        self.send_subscriptions('1', force=True)

    def _do_get_subscriptions(self, chat_id, args, update):
        """
        Handle a /get_subscriptions command.
        """
        print(self.db.get_subscriptions('1'))

    def _callback_delete(self, chat_id, args, update):
        """
        Handle the callback request of a /delete_akademie command.
        """
        if not self._check_privilege(chat_id):
            self.tclient.edit_message_text(
                'Du hast leider nicht die erforderlichen Berechtigung um diesen Befehl auszuführen :/'.format(args[1]),
                update["callback_query"]["message"]["chat"]["id"],
                update["callback_query"]["message"]["message_id"])
            return

        if len(args) > 1:
            self.db.delete_akademie(args[1])
            self.tclient.edit_message_text(
                'Akademie {} wurde gelöscht'.format(args[1]),
                update["callback_query"]["message"]["chat"]["id"],
                update["callback_query"]["message_id"])

    @staticmethod
    def _check_privilege(chat_id):
        """
        Helper function to check if the user denoted by the given chat_id has privileged access to perform management
        functions.
        :param chat_id: The chat_id to check for privileged access
        :type chat_id: int
        :return: True if the user has privileged access
        """
        return chat_id == 459053986

    def _print_akademien(self, akademien, chat_id=None):
        """
        Helper function to generate a textual list of academies to a given chat. If a chat_id is given, the list is sent
        to the Telegram Chat referenced by this id.

        :param akademien: A list of academies to be serialized into a string.
        :type akademien: [dbhelper.Akademie]
        :param chat_id: A chat to send the message to
        :type chat_id: int or None
        :return: The generated list of academies
        """
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
            self.tclient.send_message("\n".join(msg_parts), chat_id, parse_mode="Markdown")

        return msg_parts

    def _print_akademie_countdown(self, akademien, chat_id=None, pre_text=None, post_text=None):
        aka_list = []

        for a in (a for a in sorted(akademien, key=lambda x: x.date)):
            if a.name.endswith('kademie') or a.name.endswith('Aka'):
                aka_list.append('Es sind noch {} Tage bis zur {}\n\t-- _{}_\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))
            elif a.name == 'Seminar' or a.name.endswith('Segeln'):
                aka_list.append('Es sind noch {} Tage bis zum {}\n\t-- _{}_\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))
            else:
                aka_list.append('Es sind noch {} bis zur Veranstaltung {}\n\t-- _{}_\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))

        msg = '\n'.join(aka_list)
        if pre_text:
            msg = pre_text + msg
        if post_text:
            msg = msg + post_text
        if chat_id:
            self.tclient.send_message(msg, chat_id, parse_mode="Markdown")

        return msg

    def _too_much_spam(self, update):
        if update["message"]["chat"]["type"] == "private":
            return False
        elif update["message"]["chat"]["type"] == "group" or update["message"]["chat"]["type"] == "supergroup":
            last_msg = self.db.get_last_message_time(update["message"]["chat"]["id"])
            if not last_msg:
                self.db.set_last_message_time(update["message"]["chat"]["id"])
                return False
            else:
                delta = datetime.datetime.utcnow() - datetime.datetime.strptime(last_msg[0], '%Y-%m-%d %H:%M:%S.%f')
                if delta < timedelta(minutes=5):
                    print("Too much spam in chat {}".format(update["message"]["chat"]["id"]))
                    return True
                self.db.set_last_message_time(update["message"]["chat"]["id"])
                return False


def main():
    # Setup DB
    db = DBHelper('akademien.sqlite')
    db.setup()

    # Read configuration and setup Telegram client
    config = configparser.ConfigParser()
    config.read('config.ini')
    tclient = TClient(config['telegram']['token'])
    countdown_bot = CountdownBot(db, tclient)

    last_update_id = None
    now = datetime.datetime.utcnow().strftime('%H:%M')
    while True:
        updates = tclient.get_updates(last_update_id)
        try:
            if len(updates["result"]) > 0:
                last_update_id = get_last_update_id(updates) + 1
                for update in updates:
                    countdown_bot.dispatch_update(update)
            if now != datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M'):
                now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')
                countdown_bot.send_subscriptions('1')
            time.sleep(0.5)
        except KeyError:
            pass


if __name__ == "__main__":
    main()
