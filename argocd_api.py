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


def disable_auto_sync(app_name: str) -> bool:
    """
    Disable auto-sync for an ArgoCD application.
    
    Args:
        app_name: Name of the ArgoCD application
        
    Returns:
        True if auto-sync was successfully disabled, False otherwise
    """
    try:
        # First, get the current application spec
        app_data = list_application_by_name(app_name)
        if not app_data:
            print(f"Failed to retrieve application {app_name} to disable auto-sync")
            return False
        
        spec = app_data.get("spec", {})
        sync_policy = spec.get("syncPolicy", {})
        
        # If automated is not present or empty, auto-sync is already disabled
        if not sync_policy.get("automated"):
            print(f"Auto-sync is already disabled for {app_name}")
            return True
        
        # Build PATCH payload to remove automated sync
        # ArgoCD API requires us to send the full spec structure
        # We'll preserve all other fields and only modify syncPolicy
        patch_payload = {
            "spec": {
                "syncPolicy": {}
            }
        }
        
        # Preserve retry configuration if it exists
        if "retry" in sync_policy:
            patch_payload["spec"]["syncPolicy"]["retry"] = sync_policy["retry"]
        
        # Preserve syncOptions if they exist
        if "syncOptions" in sync_policy:
            patch_payload["spec"]["syncPolicy"]["syncOptions"] = sync_policy["syncOptions"]
        
        # If syncPolicy has no other fields, we can omit it or set to null
        # But for safety, we'll keep an empty object if there are no other fields
        if not patch_payload["spec"]["syncPolicy"]:
            # If no other fields, we can set syncPolicy to null to remove automated
            # But ArgoCD might need the full spec, so let's try with empty object first
            pass
        
        endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}"
        
        # Use PATCH method with merge strategy
        # ArgoCD API supports PATCH with application/json content type
        headers = _get_headers()
        headers["Content-Type"] = "application/json"
        
        # Try PATCH request
        try:
            response = requests.patch(
                url=endpoint,
                headers=headers,
                json=patch_payload,
                verify=Config.ARGOCD_VERIFY_SSL,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"Successfully disabled auto-sync for application {app_name}")
                return True
            else:
                # If PATCH doesn't work, try PUT with full spec
                print(f"PATCH failed (status {response.status_code}), trying PUT method...")
                # Build full spec for PUT
                full_spec = spec.copy()
                new_sync_policy = {}
                if "retry" in sync_policy:
                    new_sync_policy["retry"] = sync_policy["retry"]
                if "syncOptions" in sync_policy:
                    new_sync_policy["syncOptions"] = sync_policy["syncOptions"]
                
                if new_sync_policy:
                    full_spec["syncPolicy"] = new_sync_policy
                else:
                    # Remove syncPolicy entirely if no other fields
                    full_spec.pop("syncPolicy", None)
                
                put_payload = {"spec": full_spec}
                put_response = requests.put(
                    url=endpoint,
                    headers=headers,
                    json=put_payload,
                    verify=Config.ARGOCD_VERIFY_SSL,
                    timeout=30
                )
                
                if put_response.status_code == 200:
                    print(f"Successfully disabled auto-sync for application {app_name} using PUT")
                    return True
                else:
                    print(f"Failed to disable auto-sync for application {app_name}")
                    print(f"PUT Response status: {put_response.status_code}")
                    print(f"PUT Response body: {put_response.text}")
                    return False
        except RequestException as e:
            print(f"Request exception while disabling auto-sync for {app_name}: {e}")
            return False
    except Exception as e:
        print(f"Exception while disabling auto-sync for {app_name}: {e}")
        return False


def rollback_application(app_name: str, revision_id: str) -> str:
    """
    Rollback an ArgoCD application to a specific revision.
    
    Args:
        app_name: Name of the ArgoCD application
        revision_id: Revision ID to rollback to (string, will be converted to int)
        
    Returns:
        'ok' if rollback successful, 'error' otherwise
    """
    # Convert revision_id to integer (ArgoCD API requires int64)
    try:
        revision_id_int = int(revision_id)
    except (ValueError, TypeError):
        print(f"Invalid revision ID: {revision_id}. Must be a numeric value.")
        return "error"
    
    # Rollback endpoint
    endpoint = f"{Config.ARGOCD_URL}/api/v1/applications/{app_name}/rollback"
    
    # Correct payload structure - id must be an integer
    payload = {
        "name": app_name,
        "id": revision_id_int,
        "dryRun": False
    }

    # Make rollback request with error handling
    try:
        headers = _get_headers()
        response = requests.post(
            url=endpoint,
            headers=headers,
            json=payload,
            verify=Config.ARGOCD_VERIFY_SSL,
            timeout=30
        )
        
        if response.status_code == 200:
            return "ok"
        
        # Check for auto-sync error
        try:
            resp_json = response.json()
            error_code = resp_json.get("code")
            error_message = resp_json.get("message", "").lower()
            
            if error_code == 9 and "auto-sync" in error_message:
                # Auto-sync is enabled, check if we should disable it automatically
                if Config.AUTO_DISABLE_SYNC_ON_ROLLBACK:
                    print(f"Auto-sync is enabled for {app_name}. Attempting to disable it...")
                    if disable_auto_sync(app_name):
                        # Retry rollback after disabling auto-sync
                        print(f"Retrying rollback for {app_name} after disabling auto-sync...")
                        retry_response = requests.post(
                            url=endpoint,
                            headers=headers,
                            json=payload,
                            verify=Config.ARGOCD_VERIFY_SSL,
                            timeout=30
                        )
                        if retry_response.status_code == 200:
                            print(f"Rollback successful for {app_name} after disabling auto-sync")
                            return "ok"
                        else:
                            print(f"Rollback still failed for {app_name} after disabling auto-sync")
                            try:
                                retry_json = retry_response.json()
                                print(f"Retry error: {retry_json}")
                            except:
                                print(f"Retry response: {retry_response.text}")
                            return "error"
                    else:
                        print(f"Failed to disable auto-sync for {app_name}")
                        return "autosync_enabled"
                else:
                    # Auto-disable is not configured, return the error
                    return "autosync_enabled"
        except Exception as e:
            print(f"Error processing rollback response: {e}")
            pass
        
        # Other errors
        print(f"Rollback failed with status {response.status_code}")
        try:
            error_json = response.json()
            print(f"Error details: {error_json}")
        except:
            print(f"Error response: {response.text}")
        return "error"
        
    except RequestException as e:
        print(f"Request exception during rollback: {e}")
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


def get_appdetails_for_revision(
    app: Dict[str, Any], revision_id: int, revision_hash: str, history_item: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get appdetails (Helm parameters) for a specific revision.
    
    Args:
        app: Application dictionary from ArgoCD
        revision_id: Revision ID (versionId)
        revision_hash: Revision hash (git commit hash)
        history_item: Optional history item to use source from (if provided, uses this instead of current app source)
        
    Returns:
        Appdetails dictionary with Helm parameters or None if request fails
    """
    try:
        # Get app spec for project (usually doesn't change)
        spec = app.get("spec", {})
        
        # Use source from history_item if provided, otherwise use current app source
        if history_item and history_item.get("source"):
            source = history_item.get("source", {})
        else:
            source = spec.get("source", {})
        
        repo_url = source.get("repoURL", "")
        path = source.get("path", "")
        helm_config = source.get("helm", {})
        value_files = helm_config.get("valueFiles", [])
        
        if not repo_url:
            return None
        
        # URL encode the repository URL
        from urllib.parse import quote
        encoded_repo_url = quote(repo_url, safe="")
        
        # Build endpoint
        endpoint = f"{Config.ARGOCD_URL}/api/v1/repositories/{encoded_repo_url}/appdetails"
        
        # Build payload
        app_name = app.get("metadata", {}).get("name", "")
        app_project = spec.get("project", "default")
        
        # Use revision_hash as targetRevision (git commit hash)
        # The revision_hash from history_item.revision is the git commit hash
        # This is what we need for targetRevision in the appdetails API
        target_revision = revision_hash
        
        payload = {
            "source": {
                "repoURL": repo_url,
                "path": path,
                "targetRevision": target_revision,
                "helm": {
                    "valueFiles": value_files
                },
                "appName": app_name
            },
            "appName": app_name,
            "appProject": app_project,
            "sourceIndex": 0,
            "versionId": revision_id
        }
        
        response = _make_request("POST", endpoint, json_data=payload)
        
        if response and response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Failed to get appdetails for revision {revision_id}: {e}")
        return None
