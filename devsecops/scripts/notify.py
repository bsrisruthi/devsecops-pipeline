#!/usr/bin/env python3
"""
DevSecOps Pipeline Notification Script
Sends security scan results to Discord webhook
"""

import os
import sys
import json
import requests
from datetime import datetime

def get_scan_status():
    """
    Determine overall pipeline status from GitHub Actions context
    In GitHub Actions, we'll pass job statuses as environment variables
    """
    secret_scan = os.getenv('SECRET_SCAN_STATUS', 'unknown')
    container_scan = os.getenv('CONTAINER_SCAN_STATUS', 'unknown')
    iac_scan = os.getenv('IAC_SCAN_STATUS', 'unknown')
    
    return {
        'secret_scan': secret_scan,
        'container_scan': container_scan,
        'iac_scan': iac_scan
    }

def create_discord_message(statuses):
    """
    Create a formatted Discord embed message
    """
    # Determine overall status
    all_statuses = [statuses['secret_scan'], statuses['container_scan'], statuses['iac_scan']]
    
    if all(s == 'success' for s in all_statuses):
        color = 0x00FF00  # Green
        title = "✅ DevSecOps Pipeline: ALL CHECKS PASSED"
        description = "All security scans completed successfully. Safe to deploy!"
    elif 'failure' in all_statuses:
        color = 0xFF0000  # Red
        title = "❌ DevSecOps Pipeline: FAILED"
        description = "Security issues detected. Deployment blocked."
    else:
        color = 0xFFFF00  # Yellow
        title = "⚠️ DevSecOps Pipeline: WARNING"
        description = "Some checks could not complete."
    
    # Status emojis
    def status_emoji(status):
        return {
            'success': '✅',
            'failure': '❌',
            'skipped': '⏭️',
            'unknown': '❓'
        }.get(status, '❓')
    
    # Build fields
    fields = [
        {
            "name": "🔐 Secret Scanning (TruffleHog)",
            "value": f"{status_emoji(statuses['secret_scan'])} {statuses['secret_scan'].upper()}",
            "inline": True
        },
        {
            "name": "🐳 Container Scanning (Trivy)",
            "value": f"{status_emoji(statuses['container_scan'])} {statuses['container_scan'].upper()}",
            "inline": True
        },
        {
            "name": "🏗️ IaC Scanning (Checkov)",
            "value": f"{status_emoji(statuses['iac_scan'])} {statuses['iac_scan'].upper()}",
            "inline": True
        }
    ]
    
    # Get GitHub context
    repo = os.getenv('GITHUB_REPOSITORY', 'Unknown')
    run_id = os.getenv('GITHUB_RUN_ID', 'Unknown')
    actor = os.getenv('GITHUB_ACTOR', 'Unknown')
    ref = os.getenv('GITHUB_REF', 'Unknown')
    
    # Add context fields
    fields.append({
        "name": "📊 Details",
        "value": f"**Repository:** {repo}\n**Triggered by:** {actor}\n**Branch:** {ref.replace('refs/heads/', '')}",
        "inline": False
    })
    
    # Build the embed
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": fields,
        "footer": {
            "text": f"DevSecOps Pipeline • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add action URL if available
    if run_id != 'Unknown':
        embed["url"] = f"https://github.com/{repo}/actions/runs/{run_id}"
    
    return {
        "embeds": [embed],
        "username": "DevSecOps Bot"
    }

def send_to_discord(webhook_url, message):
    """
    Send message to Discord webhook
    """
    try:
        response = requests.post(
            webhook_url,
            json=message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 204:
            print("✅ Notification sent successfully to Discord")
            return True
        else:
            print(f"⚠️ Discord webhook returned status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending notification: {str(e)}")
        return False

def main():
    """
    Main execution
    """
    print("=" * 60)
    print("DevSecOps Pipeline Notification Script")
    print("=" * 60)
    
    # Get webhook URL from environment
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK_URL environment variable not set")
        sys.exit(1)
    
    # Get scan statuses
    print("\n📋 Collecting scan results...")
    statuses = get_scan_status()
    
    print(f"  Secret Scan: {statuses['secret_scan']}")
    print(f"  Container Scan: {statuses['container_scan']}")
    print(f"  IaC Scan: {statuses['iac_scan']}")
    
    # Create message
    print("\n📝 Creating notification message...")
    message = create_discord_message(statuses)
    
    # Send notification
    print("\n📤 Sending notification to Discord...")
    success = send_to_discord(webhook_url, message)
    
    if success:
        print("\n✅ Notification process completed successfully")
    else:
        print("\n⚠️ Notification process completed with warnings")
    
    print("=" * 60)

if __name__ == "__main__":
    main()

