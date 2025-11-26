"""
ArgoCD Deployment Bot - Main Application.

A Slack bot for managing ArgoCD deployments, rollbacks, and monitoring.
"""
import re
import json
import logging
import requests
from typing import Optional, Dict, Any, Match
from flask import Flask, Response, request, jsonify
from slackeventsapi import SlackEventAdapter
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import slack_api as reply
import argocd_api as argocd
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
is_valid, missing_vars = Config.validate()
if not is_valid:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    raise ValueError(f"Missing required configuration: {', '.join(missing_vars)}")

app = Flask(__name__)
slack_client = WebClient(Config.SLACK_TOKEN)
slack_event_adapter = SlackEventAdapter(
    Config.SLACK_SIGNING_SECRET, "/slack/events", app
)


def _extract_app_name_from_message(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extract application name from Slack message payload.
    
    Args:
        payload: Slack message payload
        
    Returns:
        Application name or None if not found
    """
    try:
        blocks = payload.get("original_message", {}).get("blocks", [])
        for block in blocks:
            elements = block.get("elements", [])
            for element in elements:
                sub_elements = element.get("elements", [])
                for sub_element in sub_elements:
                    if "style" in sub_element:
                        text = sub_element.get("text", "")
                        if text and not text.isdigit():
                            return text
    except (KeyError, TypeError) as e:
        logger.error(f"Failed to extract app name: {e}")
    return None


def _extract_revision_id_from_message(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extract revision ID from Slack message payload.
    
    Args:
        payload: Slack message payload
        
    Returns:
        Revision ID or None if not found
    """
    try:
        blocks = payload.get("original_message", {}).get("blocks", [])
        for block in blocks:
            elements = block.get("elements", [])
            for element in elements:
                sub_elements = element.get("elements", [])
                for sub_element in sub_elements:
                    if "style" in sub_element:
                        text = sub_element.get("text", "")
                        if text and text.isdigit():
                            return text
    except (KeyError, TypeError) as e:
        logger.error(f"Failed to extract revision ID: {e}")
    return None


def _send_deny_message(channel: str, user: str) -> None:
    """
    Send an access denied message to unauthorized users.
    
    Args:
        channel: Slack channel ID
        user: Slack user ID who attempted the action
    """
    message = {
        "channel": channel,
        "text": "Access Denied",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{user}>, :lock: *Access Denied*\n\n"
                        "You are not authorized to perform deployment operations. "
                        "Please contact your DevOps team if you need access to sync or rollback applications."
                    )
                }
            }
        ]
    }
    
    try:
        slack_client.chat_postMessage(**message)
    except SlackApiError as e:
        logger.error(f"Failed to send deny message: {e}")


def _send_confirmation_message(
    channel: str,
    bot_user: str,
    callback_id: str,
    message_text: str,
) -> None:
    """
    Send a confirmation message with Yes/No buttons.
    
    Args:
        channel: Slack channel ID
        bot_user: Bot user ID
        callback_id: Callback ID for the interaction
        message_text: Message text to display
    """
    message = {
        "channel": channel,
        "text": message_text,
        "attachments": [
            {
                "fallback": "Confirmation required",
                "callback_id": callback_id,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "confirmation",
                        "text": "Yes",
                        "type": "button",
                        "value": "yes",
                        "style": "primary",
                    },
                    {
                        "name": "confirmation",
                        "text": "No",
                        "type": "button",
                        "value": "no",
                    },
                ],
            },
        ],
    }
    
    try:
        slack_client.chat_postMessage(**message)
    except SlackApiError as e:
        logger.error(f"Failed to send confirmation message: {e}")


@slack_event_adapter.on("app_mention")
def handle_mentions(payload: Dict[str, Any]) -> Response:
    """
    Handle bot mentions in Slack channels.
    
    Args:
        payload: Slack event payload
        
    Returns:
        HTTP response
    """
    event = payload.get("event", {})
    channel = event.get("channel")
    user = event.get("user")
    
    # Ignore bot messages and messages with subtypes
    if event.get("subtype") is not None:
        return Response(status=200)
    
    if not channel or not user:
        logger.warning("Missing channel or user in event payload")
        return Response(status=200)
    
    # Extract bot user ID
    authorizations = payload.get("authorizations", [])
    if not authorizations:
        logger.warning("No authorizations in payload")
        return Response(status=200)
    
    bot_user = authorizations[0].get("user_id")
    if not bot_user:
        logger.warning("No bot user ID found")
        return Response(status=200)
    
    # Check user authorization (help command is always allowed)
    text = event.get("text", "")
    text = re.sub(r"^<.+>\s*", "", text).strip()
    
    # Allow help command without authorization check
    if re.match(r"^\s*help\s*$", text):
        reply._help_reply(channel, user, slack_client, bot_user)
        return Response(status=200)
    
    # Check authorization for all other commands
    if not Config.is_user_authorized(user):
        logger.warning(f"Unauthorized access attempt by user {user}")
        _send_deny_message(channel, user)
        return Response(status=200)
    
    # Parse commands
    if match := re.match(r"^\s*rollback_revisions\s+(\S+)$", text):
        app_name = match.group(1)
        message = f"<@{bot_user}>, To list all available revisions of `{app_name}`, reply \"yes\" to proceed, \"no\" to cancel."
        _send_confirmation_message(channel, bot_user, "rollback_revisions", message)
        
    elif match := re.match(r"^\s*sync\s+(\S+)$", text):
        app_name = match.group(1)
        message = f"<@{bot_user}>, To sync `{app_name}` deployment with latest release, reply \"yes\" to proceed, \"no\" to cancel."
        _send_confirmation_message(channel, bot_user, "sync_app", message)
        
    elif match := re.match(r"^\s*logs\s+(\S+)$", text):
        app_name = match.group(1)
        message = f"<@{bot_user}>, To download the logs of `{app_name}`, reply \"yes\" to proceed, \"no\" to cancel."
        _send_confirmation_message(channel, bot_user, "logs_app", message)
        
    elif match := re.match(r"^\s*rollback\s+(\S+)\s+(\S+)$", text):
        app_name = match.group(1)
        revision_id = match.group(2)
        message = (
            f"<@{bot_user}>, To rollback `{app_name}` deployment to revision `{revision_id}`, "
            "reply \"yes\" to proceed, \"no\" to cancel."
        )
        _send_confirmation_message(channel, bot_user, "rollback_app", message)
        
    elif re.match(r"^\s*list_apps\s*$", text):
        message = f"<@{bot_user}>, To list running apps, reply \"yes\" to proceed, \"no\" to cancel."
        _send_confirmation_message(channel, bot_user, "list_app_confirmation", message)
        
    else:
        logger.info(f"Unrecognized command: {text}")
    
    return Response(status=200)


@app.route("/health", methods=["GET"])
def health() -> Response:
    """
    Health check endpoint.
    
    Returns:
        HTTP response with health status
    """
    return jsonify({"status": "healthy", "service": "argocd-deployment-bot"}), 200


@app.route("/interactions", methods=["POST"])
def handle_interactions() -> Response:
    """
    Handle Slack interactive component callbacks (button clicks).
    
    Returns:
        HTTP response
    """
    try:
        payload = json.loads(request.form.get("payload", "{}"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse interaction payload: {e}")
        return Response(status=400)
    
    callback_id = payload.get("callback_id")
    action_value = payload.get("actions", [{}])[0].get("value")
    response_url = payload.get("response_url")
    channel_id = payload.get("channel", {}).get("id")
    user_id = payload.get("user", {}).get("id")
    
    if not callback_id or not action_value or not response_url:
        logger.warning("Missing required fields in interaction payload")
        return Response(status=200)
    
    # Check user authorization (except for "No" responses)
    if action_value != "no" and user_id and not Config.is_user_authorized(user_id):
        logger.warning(f"Unauthorized interaction attempt by user {user_id}")
        response = {
            "text": ":lock: Access Denied. You are not authorized to perform this operation. Please contact your DevOps team if you need access."
        }
        try:
            requests.post(response_url, json=response, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send authorization denial: {e}")
        return Response(status=200)
    
    # Handle "No" responses
    if action_value == "no":
        response = {"text": "Request cancelled."}
        try:
            requests.post(response_url, json=response, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send cancellation message: {e}")
        return Response(status=200)
    
    # Handle "Yes" responses
    if action_value != "yes":
        return Response(status=200)
    
    # Process different callback types
    if callback_id == "list_app_confirmation":
        applications_list = argocd.list_applications()
        if applications_list:
            reply._list_apps_table(response_url, applications_list)
        else:
            response = {"text": "Failed to retrieve the list of applications."}
            requests.post(response_url, json=response, timeout=10)
    
    elif callback_id == "rollback_revisions":
        app_name = _extract_app_name_from_message(payload)
        if app_name:
            app_data = argocd.list_application_by_name(app_name)
            if app_data:
                reply._available_rollback_table(response_url, app_data)
            else:
                response = {"text": f"Failed to retrieve revisions for `{app_name}`."}
                requests.post(response_url, json=response, timeout=10)
        else:
            response = {"text": "Could not extract application name from message."}
            requests.post(response_url, json=response, timeout=10)
    
    elif callback_id == "sync_app":
        app_name = _extract_app_name_from_message(payload)
        if app_name:
            sync_status = argocd.sync_application(app_name)
            if sync_status == "ok":
                response = {"text": f"`{app_name}` synced successfully. :white_check_mark:"}
            else:
                response = {"text": f"Failed to sync `{app_name}`. Please check ArgoCD logs."}
            requests.post(response_url, json=response, timeout=10)
        else:
            response = {"text": "Could not extract application name from message."}
            requests.post(response_url, json=response, timeout=10)
    
    elif callback_id == "rollback_app":
        app_name = _extract_app_name_from_message(payload)
        revision_id = _extract_revision_id_from_message(payload)
        
        if app_name and revision_id:
            rollback_status = argocd.rollback_application(app_name, revision_id)
            if rollback_status == "ok":
                response = {"text": f"`{app_name}` rolled back to revision `{revision_id}` successfully. :white_check_mark:"}
            elif rollback_status == "autosync_enabled":
                if Config.AUTO_DISABLE_SYNC_ON_ROLLBACK:
                    response = {
                        "text": (
                            f"`{app_name}` rollback failed: Auto-sync is enabled. "
                            "Attempted to disable auto-sync automatically but it failed. "
                            "Please disable auto-sync manually in ArgoCD and try again."
                        )
                    }
                else:
                    response = {
                        "text": (
                            f"`{app_name}` rollback failed: Auto-sync is enabled. "
                            "Please disable auto-sync in ArgoCD first, or set "
                            "`AUTO_DISABLE_SYNC_ON_ROLLBACK=True` to enable automatic disabling."
                        )
                    }
            else:
                response = {"text": f"Failed to rollback `{app_name}`. Please check ArgoCD logs."}
            requests.post(response_url, json=response, timeout=10)
        else:
            response = {"text": "Could not extract application name or revision ID from message."}
            requests.post(response_url, json=response, timeout=10)
    
    elif callback_id == "logs_app":
        app_name = _extract_app_name_from_message(payload)
        if app_name:
            log_data = argocd.logs_application(app_name)
            if log_data:
                json_objects = log_data.strip().split("\n")
                reply._logs_table(response_url, json_objects, app_name, channel_id, slack_client)
            else:
                response = {"text": f"Failed to retrieve logs for `{app_name}`."}
                requests.post(response_url, json=response, timeout=10)
        else:
            response = {"text": "Could not extract application name from message."}
            requests.post(response_url, json=response, timeout=10)
    
    return Response(status=200)


@slack_event_adapter.on("error")
def error_handler(err: Exception) -> None:
    """
    Handle Slack event adapter errors.
    
    Args:
        err: Error exception
    """
    logger.error(f"Slack event adapter error: {err}")


if __name__ == "__main__":
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )
