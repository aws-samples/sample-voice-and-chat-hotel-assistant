#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Get bearer token for MCP server testing.

Usage: python get_bearer_token.py
"""

import boto3
import requests


def get_bearer_token():
    """Get bearer token for MCP server authentication."""
    # Get stack outputs
    cloudformation = boto3.client("cloudformation")
    
    try:
        response = cloudformation.describe_stacks(StackName="HotelPmsStack")
        stack = response["Stacks"][0]
        outputs = {
            output["OutputKey"]: output["OutputValue"]
            for output in stack.get("Outputs", [])
        }
        
        client_id = outputs["CognitoClientId"]
        user_pool_id = outputs["CognitoUserPoolId"]
        
        # Extract region from user pool ID
        region = user_pool_id.split("_")[0]
        
        # Get client secret
        cognito_client = boto3.client("cognito-idp")
        client_response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id,
        )
        client_secret = client_response["UserPoolClient"]["ClientSecret"]
        
        # Get Cognito domain
        user_pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        domain = user_pool_response["UserPool"]["Domain"]
        
        # Build token URL
        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
        
        # Get access token
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        
        access_token = response.json()["access_token"]
        
        print(f"Bearer token: {access_token}")
        print(f"\nUse as Authorization header:")
        print(f"Authorization: Bearer {access_token}")
        
        return access_token
        
    except Exception as e:
        print(f"Error getting bearer token: {e}")
        return None


if __name__ == "__main__":
    get_bearer_token()
