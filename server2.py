# server2.py - Iridium SBD to Signal Bridge
# Copyright (C) 2025
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from flask import Flask, request
import binascii
import subprocess
import logging
import threading
import time
import json
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

SIGNAL_CLI_USER = "+31626146216"      # <-- jouw Signal-afzender
ROCKBLOCK_URL = "https://rockblock.rock7.com/rockblock/MT"
ROCKBLOCK_USERNAME = "dg@biodys.com"  # Replace with actual username
ROCKBLOCK_PASSWORD = "rHP-Hhq-M9s-iAz"  # Replace with actual password
ROCKBLOCK_IMEI = 301434061994700
# ROCKBLOCK_IMEI = "300434065264590"  # Replace with actual IMEI
POLL_INTERVAL = 30  # seconds
ALLOWED_NUMBERS_FILE = "signal.allowed"  # Whitelist bestand


def process_signal_async(imei, transmit_time, message, recipient):
    try:
        logging.info(f"Processing message from {imei} ({transmit_time}): {message}")
        subprocess.run([
            "signal-cli", "-u", SIGNAL_CLI_USER,
            "send", "-m", f"[Iridium:{imei}] {message}",
            recipient
        ], check=True)
        logging.info("Sent to Signal ✅")
    except Exception as e:
        logging.exception("Error sending via signal-cli")


def is_number_allowed(phone_number):
    """Check if phone number is in whitelist"""
    try:
        with open(ALLOWED_NUMBERS_FILE, 'r') as f:
            allowed_numbers = [line.strip() for line in f if line.strip()]
        return phone_number in allowed_numbers
    except FileNotFoundError:
        logging.warning(f"Whitelist file {ALLOWED_NUMBERS_FILE} not found - allowing all numbers")
        return True
    except Exception as e:
        logging.exception("Error reading whitelist")
        return False


def add_number_to_whitelist(phone_number):
    """Add phone number to whitelist file if not already present"""
    try:
        # Check if number is already in whitelist
        if is_number_allowed(phone_number):
            return True
            
        # Add number to whitelist file
        with open(ALLOWED_NUMBERS_FILE, 'a') as f:
            f.write(f"{phone_number}\n")
        
        logging.info(f"Auto-authorized phone number: {phone_number}")
        return True
        
    except Exception as e:
        logging.exception(f"Error adding {phone_number} to whitelist")
        return False


def poll_signal_messages():
    """Poll signal-cli voor nieuwe berichten"""
    logging.info("Start signal-cli polling...")
    poll_count = 0
    
    while True:
        poll_count += 1
        logging.debug(f"[POLL #{poll_count}] Starting signal-cli receive...")
        
        try:
            result = subprocess.run([
                "signal-cli", "-u", SIGNAL_CLI_USER, "-o", "json" , "receive" ], capture_output=True, text=True, timeout=10)
            
            logging.debug(f"[POLL #{poll_count}] signal-cli exit code: {result.returncode}")
            logging.debug(f"[POLL #{poll_count}] stdout length: {len(result.stdout) if result.stdout else 0}")
            logging.debug(f"[POLL #{poll_count}] stderr: {result.stderr if result.stderr else 'None'}")
            
            if result.returncode == 0 and result.stdout.strip():
                logging.info(f"[POLL #{poll_count}] Received data from signal-cli")
                lines = result.stdout.strip().split('\n')
                logging.debug(f"[POLL #{poll_count}] Found {len(lines)} JSON lines")
                
                for i, line in enumerate(lines):
                    logging.debug(f"[POLL #{poll_count}] Processing line {i+1}: {line[:100]}...")
                    try:
                        message_data = json.loads(line)
                        logging.info(f"[POLL #{poll_count}] Successfully parsed JSON, processing message")
                        process_incoming_signal_message(message_data)
                    except json.JSONDecodeError as e:
                        logging.warning(f"[POLL #{poll_count}] Kon JSON niet parsen: {line} - Error: {e}")
            else:
                if result.returncode != 0:
                    logging.debug(f"[POLL #{poll_count}] signal-cli returned non-zero exit code: {result.returncode}")
                else:
                    logging.debug(f"[POLL #{poll_count}] No new messages")
            
        except subprocess.TimeoutExpired:
            logging.debug(f"[POLL #{poll_count}] signal-cli receive timeout (normaal)")
        except Exception as e:
            logging.exception(f"[POLL #{poll_count}] Fout bij signal-cli polling")
            
        logging.debug(f"[POLL #{poll_count}] Sleeping for {POLL_INTERVAL} seconds...")
        time.sleep(POLL_INTERVAL)


def process_incoming_signal_message(message_data):
    """Process incoming Signal message"""
    try:
        logging.debug(f"[MSG] Processing incoming message data: {json.dumps(message_data, indent=2)}")
        
        envelope = message_data.get('envelope', {})
        source = envelope.get('source', 'unknown')
        timestamp = envelope.get('timestamp', 0)
        
        logging.debug(f"[MSG] Extracted envelope - source: {source}, timestamp: {timestamp}")
        
        if not is_number_allowed(source):
            logging.warning(f"[MSG] Phone number {source} not in whitelist - message blocked")
            return
        
        logging.info(f"[MSG] Phone number {source} is authorized")
        
        data_message = envelope.get('dataMessage', {})
        message_text = data_message.get('message', '')
        
        logging.debug(f"[MSG] Extracted dataMessage: {json.dumps(data_message, indent=2)}")
        logging.debug(f"[MSG] Message text: '{message_text}'")
        
        if message_text:
            logging.info(f"[MSG] New Signal message from {source}: {message_text}")
            logging.info(f"[MSG] Forwarding message to SBD gateway...")
            forward_to_sbd_gateway(source, timestamp, message_text)
        else:
            logging.debug(f"[MSG] No text message found in dataMessage")
            # Check for other types of messages
            if 'attachments' in data_message:
                logging.debug(f"[MSG] Message contains attachments: {len(data_message['attachments'])}")
            if 'reaction' in envelope:
                logging.debug(f"[MSG] Message is a reaction")
            if 'receiptMessage' in envelope:
                logging.debug(f"[MSG] Message is a receipt")
            
    except Exception as e:
        logging.exception("[MSG] Error processing Signal message")


def forward_to_sbd_gateway(sender, timestamp, message):
    """Stuur bericht door naar SBD gateway via RockBLOCK API"""
    try:
        logging.debug(f"[SBD] Forwarding message from {sender} to SBD gateway")
        logging.debug(f"[SBD] Original message: '{message}'")
        
        # Add sender phone number to message format: +31653490234:message text
        formatted_message = f"{sender}:{message}"
        logging.debug(f"[SBD] Formatted message with sender: '{formatted_message}'")
        
        # Convert message to hex
        message_hex = formatted_message.encode('utf-8').hex().upper()
        logging.debug(f"[SBD] Message in hex: {message_hex}")
        
        params = {
            'imei': ROCKBLOCK_IMEI,
            'username': ROCKBLOCK_USERNAME,
            'password': ROCKBLOCK_PASSWORD,
            'data': message_hex,
            'flush': 'yes'
        }
        
        logging.debug(f"[SBD] Request params: imei={ROCKBLOCK_IMEI}, data_length={len(message_hex)}, flush=yes")
        
        headers = {
            'accept': 'text/plain'
        }
        
        logging.info(f"[SBD] Sending POST request to {ROCKBLOCK_URL}...")
        response = requests.post(ROCKBLOCK_URL, params=params, headers=headers, timeout=10)
        
        logging.debug(f"[SBD] Response status: {response.status_code}")
        logging.debug(f"[SBD] Response headers: {dict(response.headers)}")
        logging.debug(f"[SBD] Response text: '{response.text}'")
        
        response.raise_for_status()
        
        logging.info(f"[SBD] Bericht succesvol doorgestuurd naar RockBLOCK: {response.status_code} - {response.text}")
        
    except Exception as e:
        logging.exception(f"[SBD] Fout bij doorsturen naar RockBLOCK gateway")

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    imei = request.form.get("imei")
    transmit_time = request.form.get("transmit_time")
    hex_data = request.form.get("data")

    if not hex_data:
        return "No data", 400

    try:
        message = binascii.unhexlify(hex_data).decode("utf-8", errors="replace")
    except Exception as e:
        message = "<decodering mislukt>"
        logging.exception("Fout bij hex-decodering")

    # Parse phone number from message
    recipient = SIGNAL_CLI_USER  # Fallback to sender
    actual_message = message
    
    if ":" in message:
        parts = message.split(":", 1)
        phone_number = parts[0].strip()
        actual_message = parts[1].strip()
        
        # Validate that it looks like a valid phone number
        if phone_number.startswith("+") and len(phone_number) > 5:
            recipient = phone_number
            # Auto-authorize this phone number
            add_number_to_whitelist(phone_number)

    # Start de signal-versturing in een aparte thread
    threading.Thread(
        target=process_signal_async,
        args=(imei, transmit_time, actual_message, recipient),
        daemon=True
    ).start()

    return "OK", 200  # 🚀 DIRECTE RESPONSE BINNEN 3s

# Start signal polling in aparte thread
polling_thread = threading.Thread(target=poll_signal_messages, daemon=True)
polling_thread.start()

# Start server
app.run(host="0.0.0.0", port=8999)
