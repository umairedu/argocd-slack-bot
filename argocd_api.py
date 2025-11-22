"""
ArgoCD Operations Module.

This module handles all interactions with the ArgoCD API including:
- Syncing applications
- Rolling back applications
- Fetching application logs
- Listing applications and their revisions
"""
import json
import requests
from typing import Optional, Dict, Any, List
from requests.exceptions import RequestException
from urllib3.exceptions import InsecureRequestWarning

from config import Config

# Suppress SSL warnings if SSL verification is disabled
if not Config.ARGOCD_VERIFY_SSL:
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def _get_headers() -> Dict[str, str]:
    """
    Get standard headers for ArgoCD API requests.
    
    Returns:
        dict: Headers dictionary with authorization and content-type
    """
    return {
        "Authorization": f"Bearer {Config.ARGOCD_TOKEN}",
        "Content-Type": "application/json",
    }


def _make_request(
    method: str, endpoint: str, headers: Optional[Dict[str, str]] = None, 
    json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
) -> Optional[requests.Response]:
    """
    Make HTTP request to ArgoCD API with error handling.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint URL
        headers: Optional custom headers
        json_data: Optional JSON payload for POST requests
        params: Optional query parameters
        
    Returns:
        Response object or None if request fails
    """
    if headers is None:
        headers = _get_headers()
    
    try:
        response = requests.request(
            method=method,
            url=endpoint,
            headers=headers,
            json=json_data,
            params=params,
            verify=Config.ARGOCD_VERIFY_SSL,
            timeout=30,
        )
        response.raise_for_status()
        return response
    except RequestException as e:
        print(f"ArgoCD API request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


def sync_application(app_name: str) -> str:
    """
    Sync an ArgoCD application with the latest release.
    
    Args:
        app_name: Name of the ArgoCD application to sync
        
    Returns:
        'ok' if sync successful, 'error' otherwise
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}/sync"
    response = _make_request("POST", endpoint)
    
    if response and response.status_code == 200:
        return "ok"
    return "error"


def rollback_application(app_name: str, revision_id: str) -> str:
    """
    Rollback an ArgoCD application to a specific revision.
    
    Args:
        app_name: Name of the ArgoCD application
        revision_id: Revision ID to rollback to
        
    Returns:
        'ok' if rollback successful, 'error' otherwise
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}/rollback"
    payload = {
        "name": app_name,
        "id": revision_id,
        "dryRun": False,
    }
    
    response = _make_request("POST", endpoint, json_data=payload)
    
    if response and response.status_code == 200:
        return "ok"
    return "error"


def logs_application(app_name: str) -> Optional[str]:
    """
    Fetch logs for an ArgoCD application.
    
    Args:
        app_name: Name of the ArgoCD application
        
    Returns:
        Log content as string or None if request fails
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}/logs"
    params = {"tailLines": Config.ARGOCD_LOG_TAIL_LINES}
    
    response = _make_request("GET", endpoint, params=params)
    
    if response and response.status_code == 200:
        return response.text
    return None


def list_applications() -> Optional[List[Dict[str, Any]]]:
    """
    List all ArgoCD applications.
    
    Returns:
        List of application dictionaries or None if request fails
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications"
    response = _make_request("GET", endpoint)
    
    if response and response.status_code == 200:
        data = response.json()
        return data.get("items", [])
    return None


def list_application_by_name(app_name: str) -> Optional[Dict[str, Any]]:
    """
    Get details of a specific ArgoCD application by name.
    
    Args:
        app_name: Name of the ArgoCD application
        
    Returns:
        Application dictionary or None if request fails
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}"
    response = _make_request("GET", endpoint)
    
    if response and response.status_code == 200:
        return response.json()
    return None


def get_sync_windows(app_name: str) -> Optional[Dict[str, Any]]:
    """
    Get sync windows for an ArgoCD application.
    
    Args:
        app_name: Name of the ArgoCD application
        
    Returns:
        Sync windows data or None if request fails
    """
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}/syncwindows"
    response = _make_request("GET", endpoint)
    
    if response and response.status_code == 200:
        return response.json()
    return None
