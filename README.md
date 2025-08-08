# Satellite Signal Bridge Server

A Flask-based gateway server that bridges satellite SBD (Short Burst Data) communications with Signal messaging. This server receives data from Iridium satellite communications via webhooks and forwards messages to Signal users, while also enabling two-way communication by receiving Signal messages and forwarding them via the RockBLOCK satellite gateway.

## Features

- **Bidirectional Communication**: Receives satellite messages via webhooks and forwards to Signal, and receives Signal messages to forward via satellite
- **Whitelist Security**: Phone number whitelist system to control access
- **Auto-authorization**: Automatically authorizes phone numbers that send messages via satellite
- **Real-time Processing**: Handles webhook responses within 3 seconds using asynchronous threading
- **Message Format Support**: Handles hex-encoded satellite data and plain text Signal messages
- **Extensive Debug Logging**: Comprehensive logging for monitoring and debugging including:
  - Poll round numbering and tracking
  - Signal-cli exit codes and output details
  - JSON parsing status and message counting
  - Complete message data structure logging
  - Authorization check results
  - RockBLOCK API interaction status
- **Continuous Signal Polling**: Polls Signal messages every 5 seconds for real-time forwarding

## Requirements

- Python 3.x with Flask
- `signal-cli` installed and configured
- RockBLOCK API credentials
- Iridium satellite device for SBD communications

## Configuration

Before running, update the following configuration variables in `server2.py`:

```python
SIGNAL_CLI_USER = "+31626146216"      # Your Signal sender number
ROCKBLOCK_USERNAME = "myUser"         # RockBLOCK username
ROCKBLOCK_PASSWORD = "myPass"         # RockBLOCK password
ROCKBLOCK_IMEI = "300434065264590"    # RockBLOCK device IMEI
```

## Whitelist File

Create a file named `signal.allowed` with one phone number per line:
```
+1234567890
+0987654321
```

If the whitelist file doesn't exist, all numbers are allowed by default.

## API Endpoints

### POST /webhook
Receives satellite SBD data from webhook providers.

**Parameters:**
- `imei`: Satellite device identifier
- `transmit_time`: Message transmission timestamp
- `data`: Hex-encoded message data

**Message Format:**
- Simple message: `Hello world`
- With phone number: `+1234567890:Hello from satellite`

## Installation & Usage

1. Install dependencies:
   ```bash
   pip install flask requests
   ```

2. Configure `signal-cli` for your Signal account

3. Update configuration variables in the script

4. Create whitelist file (optional)

5. Run the server:
   ```bash
   python server2.py
   ```

The server will start on `0.0.0.0:8999` and begin polling for Signal messages.

## How It Works

1. **Incoming Satellite Messages**: Webhook receives hex data, decodes to text, extracts phone number if present, and forwards to Signal
2. **Outgoing Messages**: Continuously polls Signal every 5 seconds for new messages, validates sender against whitelist, and forwards via RockBLOCK API
3. **Security**: Whitelist system prevents unauthorized access from unknown phone numbers
4. **Auto-authorization**: Phone numbers sending via satellite are automatically added to whitelist
5. **Debug Monitoring**: Extensive logging tracks all operations including Signal CLI responses, JSON parsing, message processing, and API interactions

## License

This work is licensed under CC BY-SA 4.0. To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/4.0/

**You are free to:**
- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material for any purpose, even commercially

**Under the following terms:**
- Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made
- ShareAlike — If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original

## Contributing

When contributing to this project, please ensure your contributions are also licensed under CC BY-SA 4.0.
