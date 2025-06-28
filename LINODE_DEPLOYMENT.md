# Deploying TN PDS Crawler to Linode Nanode VPS

This guide provides step-by-step instructions for deploying the Tamil Nadu PDS Crawler to a Linode Nanode VPS.

## Prerequisites

1. A Linode Nanode VPS (1 GB RAM, 1 CPU, 25 GB Storage)
2. SSH access to your Linode VPS
3. Root or sudo privileges on the VPS

## Deployment Steps

### 1. Create a Linode Nanode VPS

1. Sign up or log in to your [Linode account](https://login.linode.com/login)
2. Click "Create" and select "Linode"
3. Choose "Nanode 1GB" plan
4. Select a region close to you (e.g., Mumbai for best performance with Indian websites)
5. Choose a Linux distribution (Ubuntu 22.04 LTS recommended)
6. Set a strong root password
7. Click "Create Linode"

### 2. Connect to Your Linode VPS

```bash
ssh root@YOUR_LINODE_IP_ADDRESS
```

### 3. Upload the Project Files

On your local machine, compress the project files:

```bash
cd /path/to/tn-pds-crawler
tar -czvf tn-pds-crawler.tar.gz .
```

Upload the compressed file to your Linode VPS:

```bash
scp tn-pds-crawler.tar.gz root@YOUR_LINODE_IP_ADDRESS:/tmp/
```

On your Linode VPS, extract the files:

```bash
mkdir -p /tmp/tn-pds-crawler
tar -xzvf /tmp/tn-pds-crawler.tar.gz -C /tmp/tn-pds-crawler
```

### 4. Run the Setup Script

Make the setup script executable and run it:

```bash
chmod +x /tmp/tn-pds-crawler/linode_setup.sh
/tmp/tn-pds-crawler/linode_setup.sh
```

The setup script will:
- Install all required dependencies
- Set up the Python environment
- Configure the cron job to run the crawler daily at 7:58 PM IST
- Create and start a systemd service for the web interface

### 5. Configure Firewall (Optional but Recommended)

Allow HTTP traffic on port 8080:

```bash
ufw allow 8080/tcp
ufw enable
```

### 6. Access the Web Interface

Once the setup is complete, you can access the web interface at:

```
http://YOUR_LINODE_IP_ADDRESS:8080
```

## Monitoring and Maintenance

### View Crawler Logs

```bash
tail -f /opt/tn-pds-crawler/data/cron.log
```

### Check Service Status

```bash
systemctl status tn-pds-crawler
```

### Restart the Service

```bash
systemctl restart tn-pds-crawler
```

### View Web Server Logs

```bash
journalctl -u tn-pds-crawler
```

## Customization

### Change Crawler Schedule

To modify when the crawler runs:

```bash
crontab -e
```

Edit the cron job timing. The default is set to run at 7:58 PM IST (14:28 UTC).

### Update Shop List

To update the shops being monitored, edit the shop_list.json file:

```bash
nano /opt/tn-pds-crawler/shop_list.json
```

## Troubleshooting

### If the Web Interface is Not Accessible

1. Check if the service is running:
   ```bash
   systemctl status tn-pds-crawler
   ```

2. Verify the firewall settings:
   ```bash
   ufw status
   ```

3. Check for errors in the logs:
   ```bash
   journalctl -u tn-pds-crawler --no-pager
   ```

### If the Crawler is Not Running

1. Check the cron job:
   ```bash
   crontab -l
   ```

2. Check the crawler logs:
   ```bash
   cat /opt/tn-pds-crawler/data/cron.log
   ```

3. Try running the crawler manually:
   ```bash
   cd /opt/tn-pds-crawler
   export DISPLAY=:99
   /opt/tn-pds-crawler/venv/bin/python /opt/tn-pds-crawler/crawai_pds_selenium.py --shop-list-json /opt/tn-pds-crawler/shop_list.json --output-json /opt/tn-pds-crawler/data/shop_status_results.json --headless
   ```
