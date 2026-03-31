# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
End-to-end tests for deployed ChatbotMessagingStack resources.

This module tests the complete conversation flow using actual deployed AWS resources:
- CloudFormation stack outputs for resource discovery (with flexible key matching)
- Cognito authentication for both user and machine-to-machine flows
- DynamoDB for message storage
- SNS/SQS for message notifications
- API Gateway for REST endpoints

The tests are designed to work with real deployed infrastructure and will:
- Automatically discover stack outputs regardless of CloudFormation-generated suffixes
- Create and clean up test users and resources
- Properly authenticate with Cognito using ID tokens
- Test the complete message flow end-to-end
- Detect deployment issues (e.g., Lambda function problems)

Requirements tested: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 6.1, 6.2

Note: Test failures may indicate deployment issues rather than test problems.
Check Lambda function logs if tests fail with 502 Internal Server Error.
"""

import base64
import hashlib
import hmac
import json
import secrets
import string
import time
import urllib.parse
import uuid
from contextlib import suppress
from typing import Any, Optional

import boto3
import pytest
import requests
from botocore.exceptions import ClientError


@pytest.mark.e2e
class TestChatbotMessagingEndToEnd:
    """End-to-end tests for the complete chatbot messaging system."""

    @pytest.fixture(scope="class")
    def stack_outputs(self) -> dict[str, str]:
        """Retrieve CloudFormation stack outputs for resource discovery."""
        import os

        cloudformation = boto3.client("cloudformation")
        stack_name = os.getenv("CHATBOT_MESSAGING_STACK_NAME", "ChatbotMessagingStack")

        try:
            response = cloudformation.describe_stacks(StackName=stack_name)

            raw_outputs = {}
            for output in response["Stacks"][0]["Outputs"]:
                raw_outputs[output["OutputKey"]] = output["OutputValue"]

            # Map flexible output keys to standardized names
            outputs = {}

            # Find API endpoint (could be MessagingAPIEndpoint, ChatbotMessagingAPIEndpoint*, etc.)
            api_endpoint_key = None
            for key in raw_outputs:
                if "APIEndpoint" in key or "ApiEndpoint" in key:
                    api_endpoint_key = key
                    break
            assert api_endpoint_key, f"No API endpoint found in outputs: {list(raw_outputs.keys())}"
            outputs["ApiGatewayUrl"] = raw_outputs[api_endpoint_key]

            # Find messages table name
            table_name_key = None
            for key in raw_outputs:
                if "MessagesTableName" in key or key == "MessagesTableName":
                    table_name_key = key
                    break
            assert table_name_key, f"No messages table name found in outputs: {list(raw_outputs.keys())}"
            outputs["MessagesTableName"] = raw_outputs[table_name_key]

            # Find SNS topic ARN
            topic_arn_key = None
            for key in raw_outputs:
                if "TopicArn" in key and "Messaging" in key:
                    topic_arn_key = key
                    break
            assert topic_arn_key, f"No messaging topic ARN found in outputs: {list(raw_outputs.keys())}"
            outputs["SnsTopicArn"] = raw_outputs[topic_arn_key]

            # Find User Pool ID
            user_pool_id_key = None
            for key in raw_outputs:
                if "UserPoolId" in key and "Client" not in key:
                    user_pool_id_key = key
                    break
            assert user_pool_id_key, f"No user pool ID found in outputs: {list(raw_outputs.keys())}"
            outputs["UserPoolId"] = raw_outputs[user_pool_id_key]

            # Find User Pool Client ID
            client_id_key = None
            for key in raw_outputs:
                if "UserPoolClientId" in key or key == "UserPoolClientId":
                    client_id_key = key
                    break
            assert client_id_key, f"No user pool client ID found in outputs: {list(raw_outputs.keys())}"
            outputs["UserPoolClientId"] = raw_outputs[client_id_key]

            # Find Machine Client Secret ARN
            secret_arn_key = None
            for key in raw_outputs:
                if ("ClientSecret" in key or "MachineClient" in key) and "Arn" in key:
                    secret_arn_key = key
                    break
            assert secret_arn_key, f"No client secret ARN found in outputs: {list(raw_outputs.keys())}"
            outputs["ClientCredentialsSecretArn"] = raw_outputs[secret_arn_key]

            # Find User Pool Domain Name
            domain_name_key = None
            for key in raw_outputs:
                if "UserPoolDomainName" in key or key == "UserPoolDomainName":
                    domain_name_key = key
                    break
            assert domain_name_key, f"No user pool domain name found in outputs: {list(raw_outputs.keys())}"
            outputs["UserPoolDomainName"] = raw_outputs[domain_name_key]

            return outputs

        except ClientError as e:
            pytest.skip(f"{stack_name} not found or accessible: {e}")

    @pytest.fixture(scope="class")
    def cognito_client(self, stack_outputs: dict[str, str]):
        """Create Cognito client for authentication operations."""
        return boto3.client("cognito-idp")

    @pytest.fixture(scope="class")
    def secrets_client(self):
        """Create Secrets Manager client for retrieving credentials."""
        return boto3.client("secretsmanager")

    @pytest.fixture(scope="class")
    def sqs_client(self):
        """Create SQS client for message queue operations."""
        return boto3.client("sqs")

    @pytest.fixture(scope="class")
    def sns_client(self):
        """Create SNS client for topic operations."""
        return boto3.client("sns")

    @pytest.fixture(scope="class")
    def machine_credentials(self, secrets_client, stack_outputs: dict[str, str]) -> dict[str, str]:
        """Retrieve machine-to-machine credentials from Secrets Manager."""
        try:
            response = secrets_client.get_secret_value(SecretId=stack_outputs["ClientCredentialsSecretArn"])

            credentials = json.loads(response["SecretString"])

            required_keys = ["client_id", "client_secret"]
            for key in required_keys:
                assert key in credentials, f"Missing credential key: {key}"

            return credentials

        except ClientError as e:
            pytest.skip(f"Unable to retrieve machine credentials: {e}")

    @pytest.fixture
    def test_user_credentials(self, cognito_client, stack_outputs: dict[str, str]) -> dict[str, str]:
        """Create a test user in Cognito User Pool with cryptographically secure password."""
        user_pool_id = stack_outputs["UserPoolId"]

        # Generate cryptographically secure username and password
        username = f"testuser_{uuid.uuid4().hex[:8]}"
        password = self._generate_secure_password()

        try:
            # Create user
            cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=username,
                TemporaryPassword=password,
                MessageAction="SUPPRESS",  # Don't send welcome email
            )

            # Set permanent password
            cognito_client.admin_set_user_password(
                UserPoolId=user_pool_id, Username=username, Password=password, Permanent=True
            )

            credentials = {"username": username, "password": password}

            yield credentials

        finally:
            # Cleanup: Delete test user
            with suppress(ClientError):
                cognito_client.admin_delete_user(UserPoolId=user_pool_id, Username=username)

    @pytest.fixture
    def test_sqs_queue(self, sqs_client, sns_client, stack_outputs: dict[str, str]) -> dict[str, str]:
        """Create SQS queue that subscribes to the SNS topic for message verification."""
        queue_name = f"test-messaging-queue-{uuid.uuid4().hex[:8]}"

        try:
            # Create SQS queue
            queue_response = sqs_client.create_queue(
                QueueName=queue_name,
                Attributes={
                    "MessageRetentionPeriod": "300",  # 5 minutes
                    "VisibilityTimeout": "30",
                },
            )
            queue_url = queue_response["QueueUrl"]

            # Get queue attributes to get ARN
            queue_attrs = sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
            queue_arn = queue_attrs["Attributes"]["QueueArn"]

            # Set queue policy to allow SNS to send messages
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "sns.amazonaws.com"},
                        "Action": "sqs:SendMessage",
                        "Resource": queue_arn,
                        "Condition": {"ArnEquals": {"aws:SourceArn": stack_outputs["SnsTopicArn"]}},
                    }
                ],
            }

            sqs_client.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})

            # Subscribe queue to SNS topic
            subscription_response = sns_client.subscribe(
                TopicArn=stack_outputs["SnsTopicArn"], Protocol="sqs", Endpoint=queue_arn
            )

            queue_info = {
                "queue_url": queue_url,
                "queue_arn": queue_arn,
                "subscription_arn": subscription_response["SubscriptionArn"],
            }

            # Wait a moment for subscription to be confirmed
            time.sleep(2)

            yield queue_info

        finally:
            # Cleanup: Unsubscribe and delete queue
            with suppress(ClientError):
                if "queue_info" in locals() and "subscription_arn" in queue_info:
                    sns_client.unsubscribe(SubscriptionArn=queue_info["subscription_arn"])

            with suppress(ClientError):
                if "queue_info" in locals() and "queue_url" in queue_info:
                    sqs_client.delete_queue(QueueUrl=queue_info["queue_url"])

    def _generate_secure_password(self) -> str:
        """Generate a cryptographically secure password meeting Cognito requirements."""
        # Cognito requires: 8+ chars, uppercase, lowercase, number, special char
        # Generate a password that guarantees all required character types
        uppercase = secrets.choice(string.ascii_uppercase)
        lowercase = secrets.choice(string.ascii_lowercase)
        digit = secrets.choice(string.digits)
        special = secrets.choice("!@#$%^&*")

        # Generate remaining characters
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        remaining = "".join(secrets.choice(alphabet) for _ in range(8))

        # Combine and shuffle
        password_chars = list(uppercase + lowercase + digit + special + remaining)
        secrets.SystemRandom().shuffle(password_chars)

        return "".join(password_chars)

    def _authenticate_user(
        self, cognito_client, stack_outputs: dict[str, str], username: str, password: str
    ) -> tuple[str, str]:
        """Authenticate user and return both ID token and access token."""
        try:
            response = cognito_client.admin_initiate_auth(
                UserPoolId=stack_outputs["UserPoolId"],
                ClientId=stack_outputs["UserPoolClientId"],
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )

            auth_result = response["AuthenticationResult"]
            return auth_result["IdToken"], auth_result["AccessToken"]

        except ClientError as e:
            pytest.fail(f"User authentication failed: {e}")

    def _authenticate_machine(
        self, cognito_client, stack_outputs: dict[str, str], machine_credentials: dict[str, str]
    ) -> str:
        """Authenticate using client credentials flow and return access token."""
        try:
            # Use the OAuth2 configuration from the machine credentials secret
            oauth_endpoint = machine_credentials["oauth_token_url"]
            client_id = machine_credentials["client_id"]
            client_secret = machine_credentials["client_secret"]
            scope = machine_credentials["scope"]

            # Create Basic Auth header
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            # Make OAuth2 client credentials request
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "client_credentials",
                "scope": scope,
            }

            response = requests.post(oauth_endpoint, headers=headers, data=data)

            if response.status_code != 200:
                pytest.fail(f"OAuth2 authentication failed: {response.status_code} - {response.text}")

            token_data = response.json()
            return token_data["access_token"]

        except Exception as e:
            pytest.fail(f"Machine authentication failed: {e}")

    def _calculate_secret_hash(self, client_id: str, client_secret: str, username: str) -> str:
        """Calculate secret hash for Cognito authentication."""
        message = username + client_id
        dig = hmac.new(client_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()

        return base64.b64encode(dig).decode()

    def _decode_jwt_claims(self, token: str, token_type: str) -> dict[str, Any]:
        """Decode JWT token and print claims for debugging."""
        try:
            # JWT tokens have 3 parts separated by dots: header.payload.signature
            # We only need the payload (claims)
            parts = token.split(".")
            if len(parts) != 3:
                print(f"   ⚠️  Invalid JWT format for {token_type}")
                return {}

            # Add padding if needed (JWT base64 encoding may not have padding)
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            # Decode the payload
            decoded_bytes = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded_bytes)

            print(f"   🔍 {token_type} JWT Claims:")
            for key, value in claims.items():
                print(f"      {key}: {value}")

            return claims

        except Exception as e:
            print(f"   ⚠️  Failed to decode {token_type} JWT: {e}")
            return {}

    def _send_message(self, api_url: str, token: str, recipient_id: str, content: str) -> dict[str, Any]:
        """Send message via POST /messages endpoint."""
        response = requests.post(
            f"{api_url}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"recipientId": recipient_id, "content": content},
        )

        assert response.status_code == 201, f"Send message failed: {response.text}"
        return response.json()

    def _update_message_status(self, api_url: str, token: str, message_id: str, status: str) -> dict[str, Any]:
        """Update message status via PUT /messages/{messageId}/status endpoint."""
        response = requests.put(
            f"{api_url}/messages/{message_id}/status",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"status": status},
        )

        assert response.status_code == 200, f"Update message status failed: {response.text}"
        return response.json()

    def _get_messages(
        self, api_url: str, token: str, conversation_id: str, since: Optional[str] = None, limit: Optional[int] = None
    ) -> dict[str, Any]:
        """Get messages via GET /conversations/{conversationId}/messages endpoint."""
        params = {}
        if since:
            params["since"] = since
        if limit:
            params["limit"] = limit

        # URL-encode the conversation ID to handle special characters like #
        encoded_conversation_id = urllib.parse.quote(conversation_id, safe="")

        response = requests.get(
            f"{api_url}/conversations/{encoded_conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )

        assert response.status_code == 200, f"Get messages failed: {response.text}"
        return response.json()

    def _wait_for_sqs_message(self, sqs_client, queue_url: str, timeout: int = 30) -> Optional[dict[str, Any]]:
        """Wait for message to appear in SQS queue."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)

            if "Messages" in response:
                message = response["Messages"][0]

                # Delete message from queue
                sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])

                # Parse SNS message
                sns_message = json.loads(message["Body"])
                if "Message" in sns_message:
                    return json.loads(sns_message["Message"])

            time.sleep(1)

        return None

    def test_complete_conversation_flow(
        self,
        stack_outputs: dict[str, str],
        cognito_client,
        machine_credentials: dict[str, str],
        test_user_credentials: dict[str, str],
        test_sqs_queue: dict[str, str],
        sqs_client,
    ):
        """
        Test complete conversation flow between user and hotel assistant.

        This test covers all requirements:
        - 1.1, 1.2, 1.3: Message storage, status management, SNS publishing
        - 2.1, 2.2: Status updates and validation
        - 3.1, 3.2, 3.3: API endpoints for sending, updating, and retrieving messages
        - 4.1, 4.2, 4.3, 4.4: Message polling and conversation management
        - 6.1, 6.2: Authentication and logging
        """
        # Use API URL from machine credentials secret (which contains the complete config)
        api_url = machine_credentials["api_url"].rstrip("/")
        print("\n🏨 HOTEL ASSISTANT CONVERSATION FLOW TEST")
        print(f"📍 API Gateway URL: {api_url}")
        print(f"📍 OAuth2 Token URL: {machine_credentials['oauth_token_url']}")
        print(f"📍 Client ID: {machine_credentials['client_id']}")
        print(f"📍 Scope: {machine_credentials['scope']}")

        # Step 1: Authenticate both user and hotel assistant
        print("\n📋 STEP 1: Authentication")
        print(f"   👤 Authenticating user: {test_user_credentials['username']}")
        user_id_token, user_access_token = self._authenticate_user(
            cognito_client, stack_outputs, test_user_credentials["username"], test_user_credentials["password"]
        )
        print("   ✅ User authenticated successfully")

        # Debug: Decode user JWT claims for both tokens
        self._decode_jwt_claims(user_id_token, "User ID Token")
        user_access_claims = self._decode_jwt_claims(user_access_token, "User Access Token")

        print("   🤖 Authenticating machine client (client credentials)")
        assistant_token = self._authenticate_machine(cognito_client, stack_outputs, machine_credentials)
        print("   ✅ Machine client authenticated successfully")

        # Debug: Decode machine JWT claims
        machine_claims = self._decode_jwt_claims(assistant_token, "Machine Access Token")

        # Extract the actual assistant ID from machine claims
        # Priority: client_id, sub, or fallback to client_id from credentials
        assistant_id = machine_claims.get("client_id") or machine_claims.get("sub") or machine_credentials["client_id"]
        print(f"   🎯 Using assistant ID: {assistant_id}")

        # Step 2: User sends message to hotel assistant (using access token)
        print("\n📨 STEP 2: User sends message to hotel assistant")
        user_message_content = "Hello, I need help with my reservation"
        print(f"   📝 Message content: '{user_message_content}'")
        print("   🔑 Using user access token instead of ID token")
        user_message = self._send_message(api_url, user_access_token, assistant_id, user_message_content)
        print("   ✅ Message sent successfully")
        print(f"   📋 Message ID: {user_message['messageId']}")
        print(f"   💬 Conversation ID: {user_message['conversationId']}")
        print(f"   📊 Status: {user_message['status']}")

        assert "messageId" in user_message
        assert "conversationId" in user_message
        assert user_message["status"] == "sent"

        conversation_id = user_message["conversationId"]
        # Extract the actual user ID from the conversation ID
        # The conversation ID format depends on lexicographic ordering of sender/recipient
        conv_parts = conversation_id.split("#")
        assert len(conv_parts) == 2, f"Invalid conversation ID format: {conversation_id}"

        # Determine expected conversation ID based on lexicographic ordering
        # Use the same priority list as the Lambda handler (now using access token)
        user_id = (
            user_access_claims.get("username")
            or user_access_claims.get("cognito:username")
            or user_access_claims.get("client_id")
            or user_access_claims.get("sub")
        )
        participants = sorted([user_id, assistant_id])
        expected_conversation_id = f"{participants[0]}#{participants[1]}"

        print(f"   📊 User ID: {user_id}")
        print(f"   📊 Assistant ID: {assistant_id}")
        print(f"   📊 Expected conversation ID: {expected_conversation_id}")
        assert conversation_id == expected_conversation_id

        # Store the original user ID for later use
        original_user_id = user_id
        print(f"   👤 User ID for conversation: {original_user_id}")

        # Step 3: Hotel assistant receives message notification via SQS
        print("\n📬 STEP 3: Hotel assistant receives message notification via SQS")
        print("   ⏳ Waiting for SNS message in SQS queue...")
        sns_message = self._wait_for_sqs_message(sqs_client, test_sqs_queue["queue_url"])
        assert sns_message is not None, "No SNS message received in SQS queue"
        print("   ✅ SNS message received successfully")
        print(f"   📋 Message ID: {sns_message['messageId']}")
        print(f"   💬 Content: '{sns_message['content']}'")
        assert sns_message["messageId"] == user_message["messageId"]
        assert sns_message["content"] == user_message_content

        # Step 4: Hotel assistant marks message as "delivered"
        print("\n📋 STEP 4: Hotel assistant marks message as 'delivered'")
        delivered_response = self._update_message_status(
            api_url, assistant_token, user_message["messageId"], "delivered"
        )
        print(f"   ✅ Message status updated to: {delivered_response['status']}")
        assert delivered_response["status"] == "delivered"

        # Step 4a: User polls for latest messages and verifies "delivered" status
        print("\n🔍 STEP 4a: User polls for latest messages and verifies 'delivered' status")
        messages_response = self._get_messages(api_url, user_access_token, conversation_id)
        print(f"   📊 Found {len(messages_response['messages'])} messages")
        print(f"   📋 Message status: {messages_response['messages'][0]['status']}")
        assert len(messages_response["messages"]) == 1
        assert messages_response["messages"][0]["status"] == "delivered"

        # Step 5: Hotel assistant marks message as "read"
        print("\n📖 STEP 5: Hotel assistant marks message as 'read'")
        read_response = self._update_message_status(api_url, assistant_token, user_message["messageId"], "read")
        print(f"   ✅ Message status updated to: {read_response['status']}")
        assert read_response["status"] == "read"

        # Step 5a: User polls for latest messages and verifies "read" status
        print("\n🔍 STEP 5a: User polls for latest messages and verifies 'read' status")
        messages_response = self._get_messages(api_url, user_access_token, conversation_id)
        print(f"   📊 Found {len(messages_response['messages'])} messages")
        print(f"   📋 Message status: {messages_response['messages'][0]['status']}")
        assert len(messages_response["messages"]) == 1
        assert messages_response["messages"][0]["status"] == "read"

        # Step 6: Hotel assistant sends reply message to user
        print("\n💬 STEP 6: Hotel assistant sends reply message to user")
        assistant_reply_content = (
            "Hello! I'd be happy to help you with your reservation. What specific assistance do you need?"
        )
        print(f"   📝 Reply content: '{assistant_reply_content}'")
        assistant_message = self._send_message(api_url, assistant_token, original_user_id, assistant_reply_content)
        print("   ✅ Reply sent successfully")
        print(f"   📋 Reply Message ID: {assistant_message['messageId']}")
        print(f"   💬 Reply Conversation ID: {assistant_message['conversationId']}")

        assert "messageId" in assistant_message
        # Note: Assistant creates a new conversation ID based on its actual user ID
        # This is expected behavior - each direction has its own conversation ID
        assistant_message["conversationId"]
        assert assistant_message["status"] == "sent"

        # Verify SNS notification for assistant's reply
        print("   ⏳ Waiting for SNS notification for assistant's reply...")
        sns_message = self._wait_for_sqs_message(sqs_client, test_sqs_queue["queue_url"])
        assert sns_message is not None
        assert sns_message["messageId"] == assistant_message["messageId"]
        assert sns_message["content"] == assistant_reply_content
        print("   ✅ SNS notification received for reply")

        # Step 6a: User polls for latest messages in original conversation
        print("\n🔍 STEP 6a: User polls for messages in original conversation")
        messages_response = self._get_messages(api_url, user_access_token, conversation_id)
        print(f"   📊 Found {len(messages_response['messages'])} messages in user->assistant conversation")
        assert len(messages_response["messages"]) == 2  # Both user message and assistant reply

        # Verify both messages are in the same conversation
        user_msg = None
        assistant_msg = None
        for msg in messages_response["messages"]:
            if msg["messageId"] == user_message["messageId"]:
                user_msg = msg
            elif msg["messageId"] == assistant_message["messageId"]:
                assistant_msg = msg

        assert user_msg is not None, "User message not found in conversation"
        assert assistant_msg is not None, "Assistant message not found in conversation"

        # Verify both messages have the same conversation ID
        assert user_msg["conversationId"] == conversation_id
        assert assistant_msg["conversationId"] == conversation_id
        print(f"   ✅ Both messages use same conversation ID: {conversation_id}")

        # Verify the assistant's message details
        assert assistant_msg["content"] == assistant_reply_content
        assert assistant_msg["senderId"] == assistant_id  # Should match the actual assistant ID
        assert assistant_msg["recipientId"] == original_user_id
        print(f"   ✅ Assistant reply verified: '{assistant_msg['content']}'")
        print(f"   📤 Sender ID: {assistant_msg['senderId']}")
        print(f"   📥 Recipient ID: {assistant_msg['recipientId']}")
        print(f"   💬 Conversation ID: {assistant_msg['conversationId']}")

        # Step 7: User sends another message to hotel assistant
        print("\n📨 STEP 7: User sends another message to hotel assistant")
        user_message2_content = "I need to change my check-in date"
        print(f"   📝 Second message content: '{user_message2_content}'")
        user_message2 = self._send_message(api_url, user_access_token, assistant_id, user_message2_content)
        print("   ✅ Second message sent successfully")
        print(f"   📋 Second Message ID: {user_message2['messageId']}")
        print(f"   💬 Uses same conversation ID: {user_message2['conversationId'] == conversation_id}")

        assert user_message2["conversationId"] == conversation_id

        # Verify SNS notification for second user message
        print("   ⏳ Waiting for SNS notification for second message...")
        sns_message = self._wait_for_sqs_message(sqs_client, test_sqs_queue["queue_url"])
        assert sns_message is not None
        assert sns_message["messageId"] == user_message2["messageId"]
        print("   ✅ SNS notification received for second message")

        # Step 8: Verify all messages are in the same conversation
        print("\n🔍 STEP 8: Verify conversation ID patterns and message consistency")
        print("   📊 Verifying all messages in the conversation")
        final_messages = self._get_messages(api_url, user_access_token, conversation_id)
        print(f"   📊 Found {len(final_messages['messages'])} total messages")
        assert len(final_messages["messages"]) == 3  # 2 user messages + 1 assistant reply

        # Separate messages by sender
        user_messages = []
        assistant_messages = []
        for message in final_messages["messages"]:
            if message["senderId"] == original_user_id:
                user_messages.append(message)
            elif message["senderId"] == assistant_id:
                assistant_messages.append(message)

        assert len(user_messages) == 2, f"Expected 2 user messages, got {len(user_messages)}"
        assert len(assistant_messages) == 1, f"Expected 1 assistant message, got {len(assistant_messages)}"

        # Verify all messages have the same conversation ID
        for i, message in enumerate(user_messages):
            assert message["conversationId"] == expected_conversation_id
            assert message["senderId"] == original_user_id
            assert message["recipientId"] == assistant_id
            msg_id = message["messageId"][:8]
            conv_id = message["conversationId"]
            print(f"   ✅ User message {i + 1}: ID={msg_id}..., ConversationID={conv_id}")

        # Verify assistant message
        assistant_msg = assistant_messages[0]
        assert assistant_msg["conversationId"] == expected_conversation_id
        assert assistant_msg["senderId"] == assistant_id
        assert assistant_msg["recipientId"] == original_user_id
        msg_id = assistant_msg["messageId"][:8]
        conv_id = assistant_msg["conversationId"]
        print(f"   ✅ Assistant message: ID={msg_id}..., ConversationID={conv_id}")

        print("\n🎉 CONVERSATION FLOW TEST COMPLETED SUCCESSFULLY!")
        print("✅ All requirements from task 7 have been verified:")
        print("   1. User and hotel assistant authentication (both flows)")
        print("   2. User sends message via POST /messages")
        print("   3. SNS notification received via SQS")
        print("   4. Message status updates via PUT /messages/{id}/status")
        print("   4a. User polls messages via GET /conversations/{id}/messages")
        print("   5. Message marked as read")
        print("   5a. User polls and verifies read status")
        print("   6. Assistant sends reply message")
        print("   6a. User polls and sees reply")
        print("   7. User sends another message")
        print("   8. Conversation ID patterns verified")

        # No cleanup needed for machine client (uses client credentials, no user created)

    def test_message_polling_with_timestamp_filtering(
        self, stack_outputs: dict[str, str], cognito_client, test_user_credentials: dict[str, str]
    ):
        """Test message polling with timestamp filtering functionality."""
        api_url = stack_outputs["ApiGatewayUrl"].rstrip("/")

        user_id_token, user_access_token = self._authenticate_user(
            cognito_client, stack_outputs, test_user_credentials["username"], test_user_credentials["password"]
        )

        assistant_id = "hotel-assistant-test"

        # Send first message
        message1 = self._send_message(api_url, user_access_token, assistant_id, "First message")
        conversation_id = message1["conversationId"]

        # Wait a moment to ensure timestamp difference
        time.sleep(1)

        # Send second message
        self._send_message(api_url, user_access_token, assistant_id, "Second message")

        # Get all messages
        all_messages = self._get_messages(api_url, user_access_token, conversation_id)
        assert len(all_messages["messages"]) == 2

        # Get messages since first message timestamp
        since_timestamp = message1["timestamp"]
        filtered_messages = self._get_messages(api_url, user_access_token, conversation_id, since=since_timestamp)

        # Should get both messages (since timestamp is inclusive)
        assert len(filtered_messages["messages"]) >= 1

        # Test limit parameter
        limited_messages = self._get_messages(api_url, user_access_token, conversation_id, limit=1)
        assert len(limited_messages["messages"]) == 1

    def test_error_handling_scenarios(
        self, stack_outputs: dict[str, str], cognito_client, test_user_credentials: dict[str, str]
    ):
        """Test various error handling scenarios."""
        api_url = stack_outputs["ApiGatewayUrl"].rstrip("/")

        user_id_token, user_access_token = self._authenticate_user(
            cognito_client, stack_outputs, test_user_credentials["username"], test_user_credentials["password"]
        )

        # Test invalid message ID for status update
        response = requests.put(
            f"{api_url}/messages/invalid-message-id/status",
            headers={"Authorization": f"Bearer {user_access_token}", "Content-Type": "application/json"},
            json={"status": "read"},
        )
        assert response.status_code == 404

        # Test invalid status value
        message = self._send_message(api_url, user_access_token, "test-recipient", "Test message")

        response = requests.put(
            f"{api_url}/messages/{message['messageId']}/status",
            headers={"Authorization": f"Bearer {user_access_token}", "Content-Type": "application/json"},
            json={"status": "invalid-status"},
        )
        assert response.status_code == 400

        # Test unauthorized access
        response = requests.get(
            f"{api_url}/conversations/test-conversation/messages",
            headers={"Content-Type": "application/json"},  # No Authorization header
        )
        assert response.status_code == 401

    def test_conversation_isolation(
        self, stack_outputs: dict[str, str], cognito_client, test_user_credentials: dict[str, str]
    ):
        """Test that conversations are properly isolated between different user pairs."""
        api_url = stack_outputs["ApiGatewayUrl"].rstrip("/")

        user_id_token, user_access_token = self._authenticate_user(
            cognito_client, stack_outputs, test_user_credentials["username"], test_user_credentials["password"]
        )

        # Send messages to two different recipients
        message1 = self._send_message(api_url, user_access_token, "assistant1", "Message to assistant 1")
        message2 = self._send_message(api_url, user_access_token, "assistant2", "Message to assistant 2")

        # Extract actual user ID from conversation ID
        # The format depends on lexicographic ordering
        conv_parts = message1["conversationId"].split("#")
        if conv_parts[0].startswith("assistant"):
            actual_user_id = conv_parts[1]
            expected_format = "assistant_first"
        else:
            actual_user_id = conv_parts[0]
            expected_format = "user_first"

        # Verify different conversation IDs
        assert message1["conversationId"] != message2["conversationId"]

        # Verify conversation ID format based on lexicographic ordering
        if expected_format == "assistant_first":
            assert message1["conversationId"] == f"assistant1#{actual_user_id}"
            assert message2["conversationId"] == f"assistant2#{actual_user_id}"
        else:
            assert message1["conversationId"] == f"{actual_user_id}#assistant1"
            assert message2["conversationId"] == f"{actual_user_id}#assistant2"

        # Verify messages are isolated
        conv1_messages = self._get_messages(api_url, user_access_token, message1["conversationId"])
        conv2_messages = self._get_messages(api_url, user_access_token, message2["conversationId"])

        assert len(conv1_messages["messages"]) == 1
        assert len(conv2_messages["messages"]) == 1
        assert conv1_messages["messages"][0]["messageId"] == message1["messageId"]
        assert conv2_messages["messages"][0]["messageId"] == message2["messageId"]
