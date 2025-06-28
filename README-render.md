# Tamil Nadu PDS Crawler - Render Deployment

This document explains how to deploy the Tamil Nadu PDS Crawler to Render.com as a web service with persistent storage.

## Deployment Steps

1. **Create a Render Account**
   - Sign up at [render.com](https://render.com) if you don't have an account

2. **Deploy via Dashboard**
   - Log in to your Render dashboard
   - Click "New" and select "Blueprint"
   - Connect your GitHub repository containing this code
   - Render will automatically detect the `render.yaml` file and set up the service

3. **Manual Deployment**
   - Alternatively, you can deploy manually:
     - Create a new "Web Service" in Render
     - Connect your GitHub repo
     - Select "Docker" as the runtime
     - Set the following:
       - Build Command: `docker build -t tn-pds-crawler .`
       - Start Command: `/app/render_entrypoint.sh`
     - Add environment variable: `PORT=8080`
     - Create a disk with name "tn-pds-data" mounted at "/app/data" (at least 1GB)

4. **Verify Deployment**
   - Once deployed, Render will provide a URL for your service
   - Access the web interface at the root URL
   - Check crawler status at `/status`
   - View raw results at `/results`
   - View logs at `/logs`

## Persistent Storage

The crawler stores its results and logs in a persistent disk mounted at `/app/data`. This ensures data is preserved between deployments and container restarts.

## Scheduled Execution

The crawler is configured to run daily at 7:58 PM IST (14:28 UTC) via a cron job inside the container.

## Monitoring

- Health check endpoint: `/health`
- Status endpoint: `/status`
- Web dashboard: `/` (root URL)

## Troubleshooting

- If the crawler isn't running, check the logs at `/logs`
- You can manually trigger a crawler run by SSH'ing into the container via Render Shell
- Verify the cron job is set up correctly by running `crontab -l` in the Render Shell
