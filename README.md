# Tamil Nadu PDS Crawler

A Selenium-based web crawler for extracting data from the Tamil Nadu Public Distribution System (PDS) website.

## Features

- Extract shop details including status (online/offline)
- Extract transaction history and bill details
- Support for targeted search by district, taluk, and shop ID
- Detailed bill item extraction from transaction dialogs
- Debug screenshots and HTML snapshots
- Deployable as a cron job on Fly.io

## Requirements

- Python 3.8+
- Chrome browser
- ChromeDriver (automatically managed by webdriver-manager)

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

```python
from crawai_pds_selenium import process_shop_list_json

# Process a list of shops from a JSON file
process_shop_list_json(
    shop_list_file="data/shop_list.json", 
    output_json="data/results.json",
    headless=False  # Set to True for headless mode
)
```

### Command Line Usage

```bash
python crawai_pds_selenium.py --shop-list-json data/shop_list.json --output-json data/results.json
```

### Input JSON Format

```json
{
  "shops": [
    {
      "id": "21EB028P1",
      "district": "Sivagangai",
      "taluk": "Karaikudi (Tk)"
    },
    {
      "id": "21EB029PY",
      "district": "Sivagangai",
      "taluk": "Karaikudi (Tk)"
    }
  ],
  "options": {
    "include_details": true,
    "headless": false
  }
}
```

## Output

The crawler generates a JSON file with detailed information about each shop, including:
- Shop status (online/offline)
- Shop details
- Last transaction details
- Bill items from the transaction

## Deployment on Fly.io

This project can be deployed on Fly.io as a scheduled cron job that runs automatically.

### Prerequisites

1. Install the Fly CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Sign up and log in to Fly.io: `flyctl auth login`

### Deployment Steps

1. Configure your shop list in `shop_list.json`
2. Adjust the cron schedule in `entrypoint.sh` if needed (default is daily at 6:00 AM)
3. Deploy to Fly.io:
   ```bash
   fly launch
   ```
   - When prompted, select an app name or use the default
   - Choose a region close to you
   - Create a volume when prompted

4. To manually deploy after making changes:
   ```bash
   fly deploy
   ```

5. To view logs:
   ```bash
   fly logs
   ```

### Accessing Results

The crawler results are stored in the Fly.io volume. To access them:

```bash
fly ssh console
cat /app/data/shop_status_results.json
```

## License

MIT
