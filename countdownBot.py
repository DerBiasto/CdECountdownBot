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

    def send_message(self, text, chat_id, reply_markup=None, parse_mode="HTML"):
        text = urllib.parse.quote_plus(text)
        url = "sendMessage?text={}&chat_id={}".format(text, chat_id)
        if reply_markup:
            reply_markup = urllib.parse.quote_plus(reply_markup)
            url += "&reply_markup={}".format(reply_markup)
        if parse_mode:
            url += "&parse_mode={}".format(parse_mode)
        self._get_telegram_url(url)

    def edit_message_text(self, text, chat_id, message_id, reply_markup="HTML"):
        text = urllib.parse.quote_plus(text)
        url = "editMessageText?text={}&chat_id={}&message_id={}".format(text, chat_id, message_id)
        if reply_markup:
            reply_markup = urllib.parse.quote_plus(reply_markup)
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
    def __init__(self, db, tclient, admins):
        """
        Initialize a CountdownBot object using the given database connector and telegram client object
        :param db: A DBHelper to connect to the SQLite database
        :type db: DBHelper
        :param tclient: A TClient to send messages to the Telegram API
        :type tclient: TClient
        :param admins: A list of chat_ids that have privileged access to execute management operations
        :type admins: [int]
        """
        self.db = db
        self.tclient = tclient
        self.admins = admins

    def send_subscriptions(self, subscription, interval=None, max_age=datetime.timedelta(minutes=5)):
        """
        Send countdown messages to subscribers. By default this method sends a message for each subscription that was
        due within the last five minutes. To enlarge this period, pass another value for `max_age`. Additionally
        subscriptions can be filtered to be within a time interval. This should be used for periodic evauluation of this
        function.

        :param subscription: ?
        :type subscription: str
        :param interval: An interval between the last check/sending of subscriptions and now. Only subscriptions in this
                         interval are processed. To force sending of all subscriptions, use None.
        :type interval: (datetime.datetime, datetime.datetime) or None
        :param max_age: Maximum age of a subscription to send. To send all subscriptions, set to datetime.timedelta.max
        :type max_age: datetime.timedelta
        """
        # print("sending Subscriptions")

        subscribers = self.db.get_subscriptions(subscription)

        now = interval[1] if interval else datetime.datetime.now()

        for s in subscribers:
            # Get last subscription of the subscriber
            sub_time = datetime.datetime.combine(now.date(), datetime.datetime.strptime(s[1], "%H:%M").time())
            if sub_time > now:
                sub_time -= datetime.timedelta(days=1)

            # Check if subscription was in interval
            in_interval = interval is None or interval[0] < sub_time <= interval[1]
            not_too_old = (now - sub_time) <= max_age
            if in_interval and not_too_old:
                self._print_akademie_countdown(
                    s[0],
                    pre_text='Dies ist deine für {} Uhr(UTC) abonnierte Nachricht:\n\n'.format(s[1]))

    def dispatch_update(self, update):
        """
        Process an update received from the Telegram API in the context of this Bot.
        :param update: A Telegram update to be processed
        :type update: dict
        """
        command_handlers = {
            '/start': self._do_start,
            '/help': self._do_help,
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
                self.tclient.send_message('Unbekannter Befehl. Versuch es mal mit /help', chat_id)
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

    def _do_help(self, chat_id, args, update):
        """
        Handle a /start command. Just send a 'hello' to the user.
        """
        self.tclient.send_message(
            '/start - Initialisiere den Bot.\n'
            '/help - Zeige diese Liste an.\n'
            '/list - Liste alle gespeicherten Veranstaltungen alphabetisch auf.\n'
            '/countdown - Erstelle einen Countdown zu allen mit Datum gespeicherten Veranstaltungen. Alternativ kann der Name einer Veranstaltung angegeben werden und der Countdown wird nur zu dieser Veranstaltung erstellt.\n'
            '/subscribe - Abonniere tägliche Countdowns um eine bestimmte Uhrzeit (HH:MM) (UTC).\n'
            '/unsubscribe - Entferne alle Abonnements für diesen Chat.\n'
            '/now - Gib die aktuelle Uhrzeit (UTC) aus.\n'
            '/add_akademie - Füge eine neue Veranstaltung hinzu. (Nur mit Administratorrechten möglich).\n'
            '/delete_akademie - Lösche eine existierende Veranstaltung. (Nur mit Administratorrechten möglich).\n'
            '/edit_akademie - Editiere eine existierende Veranstaltung. (Nur mit Administratorrechten möglich).\n'
            , chat_id)

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

        name = args[1].strip() if len(args) > 1 else None
        self._print_akademie_countdown(chat_id, name_filter=name)

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
        user_id = update["message"]["from"]["id"]
        
        if not self._check_privilege(user_id):
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
        user_id = update["message"]["from"]["id"]
        
        if not self._check_privilege(user_id):
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
        user_id = update["message"]["from"]["id"]
        
        if not self._check_privilege(user_id):
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
        self.send_subscriptions('1', max_age=datetime.timedelta.max)

    def _do_get_subscriptions(self, chat_id, args, update):
        """
        Handle a /get_subscriptions command.
        """
        print(self.db.get_subscriptions('1'))

    def _callback_delete(self, chat_id, args, update):
        """
        Handle the callback request of a /delete_akademie command.
        """
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        chat_id = cq["message"]["chat"]["id"]
        msg_id = cq["message"]["message_id"]
        
        if not self._check_privilege(user_id):
            self.tclient.edit_message_text(
                'Du hast leider nicht die erforderlichen Berechtigung um diesen Befehl auszuführen :/'.format(args[1]),
                chat_id,
                msg_id)
            return

        if len(args) > 1:
            self.db.delete_akademie(args[1])
            self.tclient.edit_message_text(
                'Akademie {} wurde gelöscht'.format(args[1]),
                chat_id,
                msg_id)

    def _check_privilege(self, user_id):
        """
        Helper function to check if the user denoted by the given chat_id has privileged access to perform management
        functions.
        :param chat_id: The chat_id to check for privileged access
        :type chat_id: int
        :return: True if the user has privileged access
        """
        return user_id in self.admins

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
                msg = '\t-- <i>{}</i>\n'.format(a.description)
                msg_parts.append(msg)
            else:
                msg_parts.append('{}\n\t-- <i>{}</i>\n'.format(a.name, a.description))

        if chat_id:
            self.tclient.send_message("\n".join(msg_parts), chat_id)

        return msg_parts

    def _print_akademie_countdown(self, chat_id=None, pre_text=None, post_text=None, name_filter=None):
        akademien = [a for a in self.db.get_akademien() if a.date]
        akademien.sort(key=lambda x: x.date)
        if name_filter:
            akademien = (a for a in akademien if a.name == name_filter)
            if not akademien:
                self.tclient.send_message('Keine passende Akademie gefunden :\'(', chat_id)

        elif not akademien:
            self.tclient.send_message('Es sind noch keine Akademien mit Datum eingespeichert :\'(', chat_id)

        aka_list = []

        for a in akademien:
            if a.name.endswith('kademie') or a.name.endswith('Aka'):
                aka_list.append('Es sind noch {} Tage bis zur {}\n\t-- <i>{}</i>\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))
            elif a.name == 'Seminar' or a.name.endswith('Segeln'):
                aka_list.append('Es sind noch {} Tage bis zum {}\n\t-- <i>{}</i>\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))
            else:
                aka_list.append('Es sind noch {} bis zur Veranstaltung {}\n\t-- <i>{}</i>\n'
                                .format((a.date - datetime.datetime.today().date()).days, a.name, a.description))

        msg = '\n'.join(aka_list)
        if pre_text:
            msg = pre_text + msg
        if post_text:
            msg = msg + post_text
        if chat_id:
            self.tclient.send_message(msg, chat_id)

        return msg

    def _too_much_spam(self, update):
        chat_type = update["message"]["chat"]["type"]
        chat_id = update["message"]["chat"]["id"]
        
        if chat_type == "private":
            return False
        elif chat_type == "group" or chat_type == "supergroup":
            last_msg = self.db.get_last_message_time(chat_id)
            if not last_msg:
                self.db.set_last_message_time(chat_id)
                return False
            else:
                delta = datetime.datetime.utcnow() - datetime.datetime.strptime(last_msg[0], '%Y-%m-%d %H:%M:%S.%f')
                if delta < timedelta(minutes=5):
                    print("Too much spam in chat {}".format(chat_id))
                    return True
                self.db.set_last_message_time(chat_id)
                return False
        else:
            return False


def main():
    # Setup DB
    db = DBHelper('akademien.sqlite')
    db.setup()

    # Read configuration and setup Telegram client
    config = configparser.ConfigParser()
    config.read('config.ini')
    tclient = TClient(config['telegram']['token'])
    admins = [int(x) for x in config['telegram']['admins'].split()]
    countdown_bot = CountdownBot(db, tclient, admins)

    last_update_id = None
    last_subscription_send = datetime.datetime.min
    subscription_interval = datetime.timedelta(seconds=float(config['general'].get('interval_sub', 60)))
    subscription_max_age = datetime.timedelta(seconds=float(config['general'].get('max_age_sub', 1800)))
    while True:
        updates = tclient.get_updates(last_update_id)
        try:
            # Process updates from Telegram
            if len(updates["result"]) > 0:
                last_update_id = get_last_update_id(updates) + 1
                for update in updates["result"]:
                    countdown_bot.dispatch_update(update)

            # Send subscriptions (if subscription_interval since last check)
            now = datetime.datetime.utcnow()
            if (now - last_subscription_send) > subscription_interval:
                countdown_bot.send_subscriptions('1', (last_subscription_send, now), subscription_max_age)
                last_subscription_send = now

            # Sleep for half a second
            time.sleep(0.5)
        except KeyError:
            pass


if __name__ == "__main__":
    main()
