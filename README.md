# ArgoCD Deployment Bot

A production-ready Slack bot for managing ArgoCD deployments, rollbacks, and monitoring. This bot allows you to interact with your ArgoCD instance directly from Slack, making deployment operations more accessible to your team.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

## Why This Project?

In many organizations, production deployments don't sync automatically, and developers typically don't have direct production access due to company security policies. This creates a bottleneck where developers must loop in the DevOps team every time they need to sync a production deployment or perform a rollback.

**This bot solves that problem** by providing a secure, controlled way for authorized developers to:
- Sync production deployments without waiting for DevOps
- Rollback to previous versions when needed
- View application logs and status
- All without requiring direct production access

The bot acts as a bridge between your development team and production infrastructure, enabling faster iteration while maintaining security through user authorization controls. Only users in the allowed list can perform operations, ensuring that deployment actions remain controlled and auditable.

## Features

- **List Applications**: View all active ArgoCD applications with their current status and Git tags
- **Sync Applications**: Synchronize applications with the latest release
- **View Logs**: Download and view application logs directly in Slack
- **Rollback Management**: List available revisions and rollback to previous versions
- **Configurable Rollback Table**: Customize rollback table columns with Helm parameter fields (e.g., tag_version, replicaCount)
- **Interactive Commands**: User-friendly confirmation dialogs for all operations
- **Easy Deployment**: Helm chart included for Kubernetes deployment
- **Production Ready**: Tested and ready for production use

## Screenshots

### Help Command
<img src="screenshot/help.png" width="1000" height="600">


The bot provides a comprehensive help message showing all available commands and their usage.

### List Applications
<img src="screenshot/list_apps.png" width="1000" height="600">

View all active ArgoCD applications with their current Git tags and health status in a formatted table.

### Application Logs
<img src="screenshot/logs.png" width="1000" height="600">

Download and view application logs directly in Slack. Logs are formatted in a table and provided as a downloadable file.

## Prerequisites

- Python 3.8 or higher
- Access to an ArgoCD instance
- A Slack workspace with permissions to create apps
- ArgoCD API token with appropriate permissions

## Installation

###  Deployment

The easiest way to deploy this bot in a Kubernetes environment is using the included Helm chart.

#### Prerequisites
- Kubernetes cluster with Helm 3.x installed
- ArgoCD instance accessible from the cluster
- Slack app configured (see [Slack App Registration](#step-2-slack-app-registration))

#### Deploy with Helm

1. **Clone the Repository**

```bash
git clone git@github.com:umairedu/argocd-slack-bot.git
cd argocd-slack-bot
```

2. **Configure Values**

Edit `helm/deployment-bot/production/values.yaml`:

```yaml
# Update image tag
tag_version: "latest"  # or your specific version

# Configure environment variables
deployment_bot:
  plain:
    ARGOCD_URL: https://argocd-server.example.com
    ARGOCD_VERIFY_SSL: "False"
    ARGOCD_LOG_TAIL_LINES: "50"
    BOT_NAME: ArgoCD Deployment Bot
    BOT_DESCRIPTION: Your bot description
    ROLLBACK_TABLE_FIELDS: tag_version,replicaCount  # Optional: comma-separated Helm parameter fields
    AUTO_DISABLE_SYNC_ON_ROLLBACK: "True"  # Optional: automatically disable auto-sync on rollback
  
  secrets:
    SLACK_TOKEN: xoxb-your-slack-token
    SIGNING_SECRET: your-signing-secret
    VERIFICATION_TOKEN: your-verification-token
    ARGOCD_TOKEN: your-argocd-token
    ALLOWED_USERS: U1234567890,U0987654321  # Optional but recommended
```

3. **Deploy**

```bash
# Create namespace (if it doesn't exist)
kubectl create namespace argocd

# Install the chart
helm upgrade --install deployment-bot ./helm/deployment-bot \
  --namespace argocd \
  -f ./helm/deployment-bot/production/values.yaml 
  ```

4. **Verify Deployment**

```bash
# Check pod status
kubectl get pods -n argocd -l app.kubernetes.io/name=deployment-bot

# Check logs
kubectl logs -n argocd -l app.kubernetes.io/name=deployment-bot --follow
```

5. **Update Deployment**

```bash
helm upgrade --install deployment-bot ./helm/deployment-bot \
  --namespace argocd \
  -f ./helm/deployment-bot/production/values.yaml
```

#### Helm Chart Configuration

The Helm chart supports the following key configurations:

- **Image**: Customize the Docker image repository and tag
- **Resources**: Configure CPU and memory limits/requests
- **Service**: Configure service type and ports
- **Ingress**: Enable and configure ingress (Mandatory for Slack calls)
- **Environment Variables**: Set all bot configuration via `deployment_bot.plain` and `deployment_bot.secrets`

For detailed configuration options, see `helm/deployment-bot/production/values.yaml`.


#### Finding Slack User IDs

To find Slack user IDs for the `ALLOWED_USERS` configuration:

1. **Using Slack API** (recommended):
   ```bash
   curl -H "Authorization: Bearer $SLACK_TOKEN" \
        https://slack.com/api/users.list | jq '.members[] | {id: .id, name: .name, real_name: .real_name}'
   ```

2. **Using Slack Web UI**:
   - Right-click on a user's profile in Slack
   - Select "View profile"
   - The user ID is in the URL: `https://workspace.slack.com/team/U1234567890`

3. **Using Bot Response**:
   - Ask the bot for help: `@bot help`
   - The bot will mention users with their IDs in the format `<@U1234567890>`

## Setup Guide

### Step 1: ArgoCD API Token Generation

To generate an API token for the bot, you need to create an API account in ArgoCD and generate a token for it.

#### 1.1 Login to ArgoCD

```bash
argocd login <argocd-server-url> --username admin --grpc-web-root-path /
```

Replace `<argocd-server-url>` with your ArgoCD server URL (e.g., `127.0.0.1:8080` or `argocd.example.com`).

#### 1.2 Create API Account

First, check existing accounts:

```bash
argocd account list
```

If you need to create a new account, you can do so through the ArgoCD UI or CLI. For this example, we'll use an account named `api_bot`.

#### 1.3 Set Account Password

```bash
argocd account update-password \
  --account api_bot \
  --new-password <secure-password>
```

#### 1.4 Generate API Token

```bash
argocd account generate-token --account api_bot
```

Copy the generated token and use it as `ARGOCD_TOKEN` in your `.env` file.

#### 1.5 Configure RBAC Permissions

Edit the ArgoCD ConfigMap to grant appropriate permissions to your API account:

```bash
kubectl edit cm argocd-rbac-cm -n argocd
```

Add the following RBAC policies in the `data` section:

```yaml
data:
  policy.csv: |
    # Allow read and write access to applications
    p, role:readwrite, applications, get, */*, allow
    p, role:readwrite, applications, sync, */*, allow
    p, role:readwrite, applications, rollback, */*, allow
    p, role:readwrite, applications, logs, */*, allow
    p, role:readwrite, applications, update, */*, allow
    
    # Allow read and execute access
    p, role:readexecute, applications, get, */*, allow
    p, role:readexecute, applications, sync, */*, allow
    p, role:readexecute, applications, rollback, */*, allow
    p, role:readexecute, applications, logs, */*, allow
    p, role:readexecute, applications, update, */*, allow
    
    # Assign roles to API account
    g, api_bot, role:readwrite
    g, api_bot, role:readexecute
    
  policy.default: role:readonly
```

**Note**: Adjust the permissions based on your security requirements. The above configuration allows the bot to:
- Get application details
- Sync applications
- Rollback applications
- View application logs
- Update applications (required for `AUTO_DISABLE_SYNC_ON_ROLLBACK` feature)

Save and exit the editor. ArgoCD will automatically reload the RBAC configuration.

### Step 2: Slack App Registration

#### 2.1 Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter your app name (e.g., "ArgoCD Bot")
5. Select your workspace
6. Click **"Create App"**

#### 2.2 Configure Bot Token Scopes

1. In your app settings, go to **"OAuth & Permissions"** in the left sidebar
2. Scroll down to **"Bot Token Scopes"**
3. Add the following scopes:
   - `app_mentions:read` - Listen for bot mentions
   - `chat:write` - Send messages
   - `files:write` - Upload log files
   - `channels:read` - Read channel information
   - `groups:read` - Read private channel information
   - `im:read` - Read direct messages
   - `mpim:read` - Read group direct messages

#### 2.3 Enable Event Subscriptions

1. Go to **"Event Subscriptions"** in the left sidebar
2. Toggle **"Enable Events"** to On
3. Enter your Request URL: `https://your-domain.com/slack/events`
4. Under **"Subscribe to bot events"**, add:
   - `app_mention` - Listen for mentions of your bot

#### 2.4 Enable Interactive Components

1. Go to **"Interactivity"** in the left sidebar
2. Toggle **"Interactivity"** to On
3. Enter your Request URL: `https://your-domain.com/interactions`

#### 2.5 Install App to Workspace

1. Go to **"OAuth & Permissions"** in the left sidebar
2. Click **"Install to Workspace"**
3. Review the permissions and click **"Allow"**
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`) - this is your `SLACK_TOKEN`

#### 2.6 Get Signing Secret

1. Go to **"Basic Information"** in the left sidebar
2. Under **"App Credentials"**, find **"Signing Secret"**
3. Click **"Show"** and copy the value - this is your `SIGNING_SECRET`

#### 2.7 Get Verification Token (if needed)

1. In **"Basic Information"**, find **"Verification Token"**
2. Copy the value - this is your `VERIFICATION_TOKEN`

**Note**: Verification Token is deprecated in newer Slack apps but may still be required for some configurations.

#### 2.8 Invite Bot to Channels

Invite your bot to the channels where you want to use it:

```
/invite @YourBotName
```

## Usage

### Available Commands

Mention the bot in a channel and use one of these commands:

- `@bot list_apps` - List all active ArgoCD applications
- `@bot sync APP_NAME` - Synchronize an application with the latest release
- `@bot logs APP_NAME` - Download and view application logs
- `@bot rollback_revisions APP_NAME` - List available revisions for rollback
- `@bot rollback APP_NAME REVISION_NUMBER` - Rollback to a specific revision (automatically handles auto-sync if configured)
- `@bot help` - Show help message with all available commands

### Rollback Table Configuration

The rollback table can be customized to display additional Helm parameter fields. This is useful for showing deployment-specific information like image tags, replica counts, or other configuration values.

#### Configuration

Set the `ROLLBACK_TABLE_FIELDS` environment variable with comma-separated Helm parameter field names:

```bash
ROLLBACK_TABLE_FIELDS=tag_version,replicaCount
```

#### How It Works

1. When you run `@bot rollback_revisions APP_NAME`, the bot:
   - Fetches all available revisions from ArgoCD history
   - For each revision, calls the ArgoCD appdetails API to retrieve Helm parameters
   - Extracts the specified fields from the Helm parameters
   - Displays them as additional columns in the rollback table

2. **Default Behavior**: If `ROLLBACK_TABLE_FIELDS` is not set, the table shows only:
   - App Name
   - Revision Number
   - Last Deploy Time

3. **With Custom Fields**: When configured, the table includes the base columns plus your custom fields:
   - App Name
   - Revision Number
   - Last Deploy Time
   - tag_version (or your first field)
   - replicaCount (or your second field)
   - ... (additional fields)

#### Example

With `ROLLBACK_TABLE_FIELDS=tag_version,replicaCount`, the rollback table will display:

```
+------------+------------------+---------------------+------------+--------------+
| App Name   | Revision Number  | Last Deploy Time    | tag_version| replicaCount |
+------------+------------------+---------------------+------------+--------------+
| my-app     | 3177             | 2025-11-26T07:00:17Z| 8ecf283f   | 1            |
| my-app     | 3176             | 2025-11-26T06:49:05Z| 7d8e9f10   | 2            |
+------------+------------------+---------------------+------------+--------------+
```

#### Notes

- Field names must match exactly the Helm parameter names in your values.yaml
- If a field is not found for a revision, "N/A" will be displayed
- The API call is made for each revision, so response time may increase with many revisions
- Only Helm-based applications support this feature

### Auto-Sync Handling for Rollbacks

ArgoCD prevents rollbacks when auto-sync is enabled for an application. The bot can automatically handle this situation.

#### Configuration

Set the `AUTO_DISABLE_SYNC_ON_ROLLBACK` environment variable to enable automatic auto-sync disabling:

```bash
AUTO_DISABLE_SYNC_ON_ROLLBACK=True
```

#### How It Works

1. **When Rollback Fails Due to Auto-Sync**:
   - The bot detects the auto-sync error (code 9)
   - If `AUTO_DISABLE_SYNC_ON_ROLLBACK=True`, it automatically disables auto-sync for the application
   - The bot then retries the rollback operation
   - If successful, the rollback completes

2. **When Auto-Disable is Not Configured**:
   - The bot returns an error message indicating auto-sync is enabled
   - You must manually disable auto-sync in ArgoCD before attempting rollback

3. **What Gets Preserved**:
   - When disabling auto-sync, the bot preserves:
     - Retry configuration
     - Sync options
     - Other sync policy settings
   - Only the `automated` field is removed

#### Example Flow

```
User: @bot rollback my-app 12345
Bot: Auto-sync is enabled for my-app. Attempting to disable it...
Bot: Successfully disabled auto-sync for application my-app
Bot: Retrying rollback for my-app after disabling auto-sync...
Bot: `my-app` rolled back to revision `12345` successfully. ✅
```

#### Important Notes

- **Auto-sync remains disabled** after the rollback. You may want to re-enable it manually if needed
- The bot requires appropriate ArgoCD RBAC permissions to modify application sync policies
- If auto-sync disabling fails, the bot will return an error message with instructions
- This feature only works if the ArgoCD API account has permissions to update application specs

### Examples

```
@argocd-bot list_apps
@argocd-bot sync my-app
@argocd-bot logs my-app
@argocd-bot rollback_revisions my-app
@argocd-bot rollback my-app 12345
@argocd-bot help
```

## Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_TOKEN` | Yes | - | Slack bot OAuth token |
| `SIGNING_SECRET` | Yes | - | Slack app signing secret |
| `VERIFICATION_TOKEN` | Yes | - | Slack verification token |
| `ARGOCD_TOKEN` | Yes | - | ArgoCD API token |
| `ARGOCD_URL` | Yes | - | ArgoCD server URL |
| `ALLOWED_USERS` | No* | - | Comma-separated list of Slack user IDs allowed to use the bot |
| `BOT_NAME` | No | "ArgoCD Deployment Bot" | Custom bot name |
| `BOT_DESCRIPTION` | No | Default description | Custom bot description |
| `FLASK_HOST` | No | "0.0.0.0" | Flask server host |
| `FLASK_PORT` | No | "5000" | Flask server port |
| `FLASK_DEBUG` | No | "False" | Enable Flask debug mode |
| `ARGOCD_VERIFY_SSL` | No | "False" | Verify SSL certificates |
| `ARGOCD_LOG_TAIL_LINES` | No | "50" | Number of log lines to fetch |
| `ROLLBACK_TABLE_FIELDS` | No | - | Comma-separated list of Helm parameter field names to display in rollback table (e.g., `tag_version,replicaCount`) |
| `AUTO_DISABLE_SYNC_ON_ROLLBACK` | No | "False" | Automatically disable auto-sync when rollback fails due to auto-sync being enabled |

\* **Required for production**: If not set, all users will be allowed (not recommended for production environments).

## Security Considerations

1. **User Authorization**: **CRITICAL** - Always configure `ALLOWED_USERS` in production to restrict bot access to authorized personnel only. Without this setting, any user in your Slack workspace can perform deployment operations.

2. **Token Security**: Never commit tokens or secrets to version control. Use environment variables or secret management systems.

3. **RBAC Permissions**: Configure ArgoCD RBAC to grant only the minimum required permissions to the API account.

4. **Network Security**: In production, ensure the bot is only accessible from trusted networks and use HTTPS.

5. **SSL Verification**: Enable `ARGOCD_VERIFY_SSL=True` in production to verify ArgoCD SSL certificates.

6. **Slack Security**: Use Slack's signing secret verification (already implemented) to verify request authenticity.

### User Authorization

The bot implements user authorization to ensure only authorized users can perform deployment operations:

- **Configuration**: Set `ALLOWED_USERS` environment variable with comma-separated Slack user IDs
- **Behavior**: 
  - Authorized users can use all bot commands (except `help` which is available to everyone)
  - Unauthorized users receive an access denied message when attempting to use the bot
  - Authorization is checked both for command mentions and button interactions
- **Help Command**: The `help` command is available to all users (no authorization required)
- **Logging**: All unauthorized access attempts are logged for security auditing

## Troubleshooting

### ArgoCD API errors

- Verify `ARGOCD_TOKEN` is valid and not expired
- Check ArgoCD RBAC permissions for the API account
- Ensure `ARGOCD_URL` is correct and accessible
- Verify SSL settings if using HTTPS

## Project Structure

```
argocd-slack-bot/
├── helm/                      # Helm chart for Kubernetes deployment
│   └── deployment-bot/
│       ├── Chart.yaml
│       ├── production/
│       │   └── values.yaml    # Production configuration
│       └── templates/         # Kubernetes manifests
├── screenshot/                # Screenshots for documentation
│   ├── help.png
│   ├── list_apps.png
│   └── logs.png
├── main.py                    # Main application entry point
├── slack_api.py               # Slack API interaction handlers
├── argocd_api.py              # ArgoCD API client
├── config.py                  # Configuration management
├── Dockerfile                 # Docker image definition
├── requirements.txt           # Python dependencies
├── env.example               # Environment variables template
└── README.md                 # This file
```
