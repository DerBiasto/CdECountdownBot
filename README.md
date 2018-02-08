# CdECountdownBot

## Setup

```
# Setup virtual environment and dependencies
virtualenv -p python3 env
. env/bin/activate
pip3 install -r requirements
deactivate

# Configure countdownBot
cp config.ini.sample config.ini
$EDITOR config.ini
```

Insert Telegram API token and space-seperated list of admin user_ids into config.ini.

## Start

```
env/bin/activate
python3 countdownBot.py
```