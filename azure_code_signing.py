#!/usr/bin/env python
"""
Simple Azure code signing script for skellycam executables.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import EnvironmentCredential
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError

# Basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hardcoded configuration
ENDPOINT = "https://eus.codesigning.azure.net/"
FILE_TO_SIGN = "skellycam-ui/skellycam_server.exe"
FILE_DIGEST = "SHA256"
TIMESTAMP_URL = "http://timestamp.acs.microsoft.com"
TIMESTAMP_DIGEST = "SHA256"


def main():
    # Load secrets from .env file
    load_dotenv()

    # Check for required environment variables
    required_vars = [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "TRUSTED_SIGNING_ACCOUNT_NAME",
        "CERTIFICATE_PROFILE_NAME"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please add them to your .env file")
        sys.exit(1)

    # Verify file exists
    file_path = Path(FILE_TO_SIGN)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    logger.info(f"Signing file: {file_path}")

    try:
        # Get credentials using Azure Identity
        credential = EnvironmentCredential()

        # Get access token for Trusted Signing service
        token = credential.get_token("https://codesigning.azure.net/.default")

        # Sign the file
        sign_file(file_path, token.token)

        logger.info(f"Successfully signed: {file_path}")
        logger.info("Done!")

    except ClientAuthenticationError as e:
        logger.error(f"Authentication failed: {str(e)}")
        sys.exit(1)
    except ServiceRequestError as e:
        logger.error(f"Service request failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


def sign_file(file_path: Path, access_token: str):
    """Sign a file using Azure Trusted Signing service."""
    import requests

    # Read file content
    with open(file_path, "rb") as f:
        file_content = f.read()

    # Prepare signing request
    sign_url = f"{ENDPOINT}/accounts/{os.getenv('TRUSTED_SIGNING_ACCOUNT_NAME')}/sign"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "certificateProfileName": os.getenv("CERTIFICATE_PROFILE_NAME"),
        "fileDigest": FILE_DIGEST,
        "timestampRfc3161": TIMESTAMP_URL,
        "timestampDigest": TIMESTAMP_DIGEST,
        "files": [
            {
                "fileName": file_path.name,
                "content": file_content.hex()  # Convert binary to hex
            }
        ]
    }

    # Send signing request
    response = requests.post(sign_url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Signing failed: {response.text}")

    # Save signed file
    signed_content = bytes.fromhex(response.json()["files"][0]["signedContent"])
    with open(file_path, "wb") as f:
        f.write(signed_content)


if __name__ == "__main__":
    main()