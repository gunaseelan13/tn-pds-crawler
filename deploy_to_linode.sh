#!/bin/bash
# Script to deploy TN PDS Crawler to an existing Linode Nanode VPS

# Configuration - EDIT THESE VALUES
LINODE_IP="172.232.121.32"  # Your Linode Nanode IP address
SSH_USER="root"  # SSH username (usually root for new Linode instances)
SSH_KEY=""  # Path to your SSH key file (leave empty if using password authentication)

# Check if IP address is provided
if [ -z "$LINODE_IP" ]; then
    echo "Please edit this script and set your LINODE_IP address"
    exit 1
fi

# Prepare SSH command
if [ -n "$SSH_KEY" ]; then
    SSH_CMD="ssh -i $SSH_KEY $SSH_USER@$LINODE_IP"
else
    SSH_CMD="ssh $SSH_USER@$LINODE_IP"
fi

echo "Packaging TN PDS Crawler application..."
# Create a temporary directory for packaging
mkdir -p /tmp/tn-pds-deploy
rm -rf /tmp/tn-pds-deploy/*

# Copy all necessary files to the temp directory
cp -r ./* /tmp/tn-pds-deploy/
cd /tmp/tn-pds-deploy

# Remove unnecessary files and directories
rm -rf venv __pycache__ .git .github .gitignore
rm -f *.tar.gz

# Create the tarball
tar -czf tn-pds-crawler.tar.gz .
cd -

echo "Transferring files to Linode Nanode VPS at $LINODE_IP..."
if [ -n "$SSH_KEY" ]; then
    scp -i $SSH_KEY /tmp/tn-pds-deploy/tn-pds-crawler.tar.gz $SSH_USER@$LINODE_IP:/tmp/
else
    scp /tmp/tn-pds-deploy/tn-pds-crawler.tar.gz $SSH_USER@$LINODE_IP:/tmp/
fi

echo "Setting up TN PDS Crawler on the remote server..."
$SSH_CMD "mkdir -p /tmp/tn-pds-crawler && \
          tar -xzf /tmp/tn-pds-crawler.tar.gz -C /tmp/tn-pds-crawler && \
          chmod +x /tmp/tn-pds-crawler/linode_setup.sh && \
          /tmp/tn-pds-crawler/linode_setup.sh"

echo "Deployment complete!"
echo "You can access the web interface at http://$LINODE_IP:8080"
echo "The crawler will run daily at 7:58 PM IST (14:28 UTC)"
