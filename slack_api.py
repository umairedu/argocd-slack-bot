"""
Slack Reply Module.

This module handles formatting and sending responses to Slack,
including help messages, application lists, rollback tables, and logs.
"""
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from prettytable import PrettyTable
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import Config
import argocd_api as argocd


def _help_reply(channel: str, user: str, client: WebClient, bot_user: str) -> None:
    """
    Send help message with available commands.
    
    Args:
        channel: Slack channel ID
        user: Slack user ID who requested help
        client: Slack WebClient instance
        bot_user: Bot user ID
    """
    message = {
        "channel": channel,
        "text": "Available Commands",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user}> :wave:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Welcome to the {Config.BOT_NAME}, {Config.BOT_DESCRIPTION} "
                        "Here are the available commands:"
                    )
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"• <@{bot_user}> `list_apps` - *List all active applications "
                        "in the ArgoCD environment.*\n"
                        f"• <@{bot_user}> `sync APP_NAME` - *Synchronize the specified "
                        "application with the latest release.*\n"
                        f"• <@{bot_user}> `logs APP_NAME` - *Download pod logs for the "
                        "given application.*\n"
                        f"• <@{bot_user}> `rollback_revisions APP_NAME` - *Show available "
                        "revisions for rolling back the specified application.*\n"
                        f"• <@{bot_user}> `rollback APP_NAME REVISION_NUMBER` - *Rollback "
                        "the specified application to the specified revision.*\n"
                        f"• <@{bot_user}> `help` - *Show this help message.*"
                    )
                }
            }
        ]
    }
    
    try:
        client.chat_postMessage(**message)
    except SlackApiError as e:
        print(f"Failed to send help message: {e}")


def _list_apps_table(response_url: str, applications_list: List[Dict[str, Any]]) -> None:
    """
    Format and send application list as a table.
    
    Args:
        response_url: Slack response URL for updating the message
        applications_list: List of application dictionaries from ArgoCD
    """
    table = PrettyTable()
    table.field_names = ["App Name", "Git Tag", "Status"]
    table.align = "l"
    
    for app in applications_list:
        app_name = app.get("metadata", {}).get("name", "Unknown")
        status = app.get("status", {})
        health_status = status.get("health", {}).get("status", "Unknown")
        
        git_tag = "Not Found"
        summary = status.get("summary", {})
        if "images" in summary and summary["images"]:
            git_tag = summary["images"][0].split(":")[-1]
        
        table.add_row([app_name, git_tag, health_status])
    
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{table.get_string()}```"
                }
            }
        ]
    }
    
    try:
        requests.post(response_url, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"Failed to send application list: {e}")


def _available_rollback_table(
    response_url: str, app: Dict[str, Any]
) -> None:
    """
    Format and send available rollback revisions as a table.
    
    Args:
        response_url: Slack response URL for updating the message
        app: Application dictionary from ArgoCD
    """
    # Build base field names
    field_names = ["App Name", "Revision Number", "Last Deploy Time"]
    
    # Add additional fields from environment variable
    additional_fields = Config.ROLLBACK_TABLE_FIELDS
    if additional_fields:
        field_names.extend(additional_fields)
    
    table = PrettyTable()
    table.field_names = field_names
    table.align = "l"
    
    app_name = app.get("metadata", {}).get("name", "Unknown")
    status = app.get("status", {})
    history = status.get("history", [])
    
    # Loop through each revision in history
    for history_item in history:
        revision_id = history_item.get("id", "Unknown")
        deployed_at = history_item.get("deployedAt", "Unknown")
        revision_hash = history_item.get("revision", "")
        
        # Fallback: try to get revision from source if not directly available
        if not revision_hash:
            source = history_item.get("source", {})
            revision_hash = source.get("targetRevision", "")
        
        # Start building row with base fields
        row = [app_name, revision_id, deployed_at]
        
        # Fetch additional fields if configured
        if additional_fields and revision_id != "Unknown" and revision_hash:
            try:
                # Get appdetails for this revision
                appdetails = argocd.get_appdetails_for_revision(
                    app, revision_id, revision_hash
                )
                
                # Extract Helm parameters
                helm_params = {}
                if appdetails:
                    helm_data = appdetails.get("helm", {})
                    parameters = helm_data.get("parameters", [])
                    for param in parameters:
                        param_name = param.get("name", "")
                        param_value = param.get("value", "")
                        if param_name:
                            helm_params[param_name] = param_value
                
                # Add values for each additional field
                for field in additional_fields:
                    value = helm_params.get(field, "N/A")
                    row.append(str(value) if value else "N/A")
            except Exception as e:
                print(f"Failed to fetch additional fields for revision {revision_id}: {e}")
                # Add N/A for each additional field if fetch fails
                row.extend(["N/A"] * len(additional_fields))
        elif additional_fields:
            # If revision_id is Unknown or revision_hash is missing, add N/A for all fields
            row.extend(["N/A"] * len(additional_fields))
        
        table.add_row(row)
    
    table_string = table.get_string(sortby="Revision Number", reversesort=True)
    
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{table_string}```"
                }
            }
        ]
    }
    
    try:
        requests.post(response_url, json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"Failed to send rollback table: {e}")


def _logs_table(
    response_url: str,
    json_objects: List[str],
    app_name: str,
    channel_id: str,
    slack_client: WebClient,
) -> None:
    """
    Format and send application logs as a file upload.
    
    Args:
        response_url: Slack response URL for updating the message
        json_objects: List of JSON log strings
        app_name: Name of the application
        channel_id: Slack channel ID
        slack_client: Slack WebClient instance
    """
    table = PrettyTable()
    table.field_names = ["Stream", "Pod Name", "Time"]
    table.align = "l"
    
    for json_str in json_objects:
        try:
            log_data = json.loads(json_str)
            result = log_data.get("result", {})
            
            # Handle None values explicitly - .get() returns None if key exists with None value
            # Convert to string to ensure all values are strings for sorting
            content = str(result.get("content") or "")
            timestamp = str(result.get("timeStamp") or "Unknown")
            pod_name = str(result.get("podName") or "Unknown")
            
            if content:
                table.add_row([content[:100], pod_name, timestamp])  # Truncate long content
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse log entry: {e}")
            continue
    
    # Only sort if table has rows
    if len(table.rows) > 0:
        table_string = table.get_string(sortby="Time", reversesort=False)
    else:
        table_string = table.get_string()
    
    # Send initial message
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Please download the last {Config.ARGOCD_LOG_TAIL_LINES} lines of logs :file_folder:"
                }
            }
        ]
    }
    
    try:
        requests.post(response_url, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"Failed to send log message: {e}")
    
    # Create log file
    log_dir = Path("/tmp")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{app_name}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.logs"
    
    try:
        # Write table content to file
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(table_string)
        
        slack_client.files_upload_v2(
            channel=channel_id,
            title=f"Logs for {app_name}",
            file=str(log_file),
            initial_comment=f"Logs for {app_name}",
        )
        
        # Clean up
        log_file.unlink()
    except (SlackApiError, IOError) as e:
        print(f"Failed to upload log file: {e}")
