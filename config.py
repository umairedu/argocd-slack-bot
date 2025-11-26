"""
Configuration management for ArgoCD Deployment Bot.

This module centralizes all configuration settings and environment variables.
"""
import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration class."""
    
    # Slack Configuration
    SLACK_TOKEN: Optional[str] = os.getenv("SLACK_TOKEN")
    SLACK_SIGNING_SECRET: Optional[str] = os.getenv("SIGNING_SECRET")
    SLACK_VERIFICATION_TOKEN: Optional[str] = os.getenv("VERIFICATION_TOKEN")
    
    # ArgoCD Configuration
    ARGOCD_TOKEN: Optional[str] = os.getenv("ARGOCD_TOKEN")
    ARGOCD_URL: Optional[str] = os.getenv("ARGOCD_URL")
    
    # Bot Configuration
    BOT_NAME: str = os.getenv("BOT_NAME", "ArgoCD Deployment Bot")
    BOT_DESCRIPTION: str = os.getenv(
        "BOT_DESCRIPTION",
        "ArgoCD Deployment Bot, designed to assist you with production deployment, "
        "rollback procedures, and status checks for current deployments and tags."
    )
    
    # Flask Configuration
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    # ArgoCD API Configuration
    ARGOCD_VERIFY_SSL: bool = os.getenv("ARGOCD_VERIFY_SSL", "False").lower() == "true"
    ARGOCD_LOG_TAIL_LINES: int = int(os.getenv("ARGOCD_LOG_TAIL_LINES", "50"))
    AUTO_DISABLE_SYNC_ON_ROLLBACK: bool = os.getenv("AUTO_DISABLE_SYNC_ON_ROLLBACK", "False").lower() == "true"
    
    # Rollback Table Configuration
    ROLLBACK_TABLE_FIELDS: List[str] = [
        field.strip()
        for field in os.getenv("ROLLBACK_TABLE_FIELDS", "").split(",")
        if field.strip()
    ]
    
    # User Authorization
    ALLOWED_USERS: List[str] = [
        user_id.strip() 
        for user_id in os.getenv("ALLOWED_USERS", "").split(",") 
        if user_id.strip()
    ]
    
    @classmethod
    def is_user_authorized(cls, user_id: str) -> bool:
        """
        Check if a user is authorized to use the bot.
        
        Args:
            user_id: Slack user ID to check
            
        Returns:
            True if user is authorized, False otherwise
        """
        if not cls.ALLOWED_USERS:
            # If no allowed users configured, allow all (backward compatibility)
            return True
        return user_id in cls.ALLOWED_USERS
    
    @classmethod
    def validate(cls) -> Tuple[bool, List[str]]:
        """
        Validate required configuration values.
        
        Returns:
            tuple: (is_valid, list_of_missing_keys)
        """
        required_vars = [
            ("SLACK_TOKEN", cls.SLACK_TOKEN),
            ("SIGNING_SECRET", cls.SLACK_SIGNING_SECRET),
            ("ARGOCD_TOKEN", cls.ARGOCD_TOKEN),
            ("ARGOCD_URL", cls.ARGOCD_URL),
        ]
        
        missing = [name for name, value in required_vars if not value]
        return len(missing) == 0, missing

