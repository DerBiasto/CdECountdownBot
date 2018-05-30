import logging
import requests
import json
import time
import datetime
import urllib.parse

logger = logging.getLogger(__name__)

class TClient:
	URL = "https://api.telegram.org/bot{}/{}"

	def __init__(self, token):
		self.token = token
		self.last_update_id = None

	def _get_json_from_url(self, url):
		try:
			response = requests.get(self.URL.format(self.token, url))
			content = response.content.decode("utf8")
			js = json.loads(content)
		except Exception as e:
			logger.error("Error while trying to access Telegram url '{}':".format(url), exc_info=e)
			return {}

		return js

	def get_updates(self, timeout):
		url = "getUpdates?timeout={}".format(timeout)
		if self.last_update_id:
			url += "&offset={}".format(self.last_update_id)
		result = self._get_json_from_url(url)

		# Log and Return on error
		if 'ok' not in result or not result['ok']:
			logger.error("Error while fetching Telegram updates: {}".format(
				result['description'] if 'description' in result else '-- unknown --'))
			return []

		if result['result']:
			self.last_update_id = self._get_last_update_id(result['result']) + 1
		return result['result']

	def send_message(self, text, chat_id, reply_markup=None, parse_mode="HTML"):
		text = urllib.parse.quote_plus(text)
		url = "sendMessage?text={}&chat_id={}".format(text, chat_id)
		if reply_markup:
			reply_markup = urllib.parse.quote_plus(reply_markup)
			url += "&reply_markup={}".format(reply_markup)
		if parse_mode:
			url += "&parse_mode={}".format(parse_mode)
		result = self._get_json_from_url(url)
		
		# Check result and log errors
		if 'ok' not in result or not result['ok']:
			logger.error("Error while sending message to Telegram API: {}".format(
				result['description'] if 'description' in result else '-- unknown --'))
				
	def send_sticker(self, sticker, chat_id):
		url = "sendSticker?sticker={}&chat_id={}".format(sticker, chat_id)
		result = self._get_json_from_url(url)
		
		# Check result and log errors
		if 'ok' not in result or not result['ok']:
			logger.error("Error while sending Sticker to Telegram API: {}".format(
				result['description'] if 'description' in result else '-- unknown --'))
		
	def edit_message_text(self, text, chat_id, message_id, reply_markup=None, parse_mode="HTML"):
		text = urllib.parse.quote_plus(text)
		url = "editMessageText?text={}&chat_id={}&message_id={}".format(text, chat_id, message_id)
		if reply_markup:
			reply_markup = urllib.parse.quote_plus(reply_markup)
			url += "&reply_markup={}".format(reply_markup)
		if parse_mode:
			url += "&parse_mode={}".format(parse_mode)
		result = self._get_json_from_url(url)

		# Check result and log errors
		if 'ok' not in result or not result['ok']:
			logger.error("Error while editing message via Telegram API: {}".format(
				result['description'] if 'description' in result else '-- unknown --'))

	def delete_message(self, chat_id, message_id):
		url = "deleteMessage?chat_id={}&message_id={}".format(text, chat_id, message_id)
		result = self._get_json_from_url(url)

		# Check result and log errors
		if 'ok' not in result or not result['ok']:
			logger.error("Error while deleting message via Telegram API: {}".format(
				result['description'] if 'description' in result else '-- unknown --'))

	@staticmethod
	def _get_last_update_id(updates):
		return max(u['update_id'] for u in updates)

