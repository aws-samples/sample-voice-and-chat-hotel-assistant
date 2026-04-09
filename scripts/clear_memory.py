#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# /// script
# dependencies = [
#     "boto3>=1.40.64",
# ]
# ///
"""
Clear AgentCore Memory events for the Virtual Assistant project.

This script:
1. Looks up the Memory ID from VirtualAssistantStack CloudFormation outputs
2. Lists all actors (or uses provided actor IDs)
3. Asynchronously deletes all memory events for each actor/session
4. Optionally stops AgentCore Runtime sessions found in memory

Usage:
    # Clear all actors (auto-detect memory ID from stack)
    uv run scripts/clear_memory.py --all-actors

    # Clear specific actors (user IDs)
    uv run scripts/clear_memory.py user1 user2 user3

    # Specify memory ID directly
    uv run scripts/clear_memory.py --memory-id mem-abc123 --all-actors

    # Limit concurrent deletions to avoid rate limits
    uv run scripts/clear_memory.py --all-actors --max-concurrent 5

    # Specify custom stack name
    uv run scripts/clear_memory.py --stack-name MyStack --all-actors

    # Dry run (show what would be deleted)
    uv run scripts/clear_memory.py --all-actors --dry-run

    # Also stop runtime sessions found in memory
    uv run scripts/clear_memory.py --all-actors --stop-sessions

    # Stop sessions with explicit runtime ARN
    uv run scripts/clear_memory.py --all-actors --stop-sessions --agent-runtime-arn arn:aws:...
"""

import argparse
import asyncio
import sys
from typing import List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def get_memory_id_from_stack(stack_name: str = "VirtualAssistantStack") -> str:
    """
    Get the Memory ID from CloudFormation stack outputs.

    Args:
        stack_name: Name of the CloudFormation stack (default: VirtualAssistantStack)

    Returns:
        Memory ID string

    Raises:
        SystemExit: If stack or output not found
    """
    cfn = boto3.client("cloudformation")

    try:
        response = cfn.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])

        if not stacks:
            print(f"Error: Stack '{stack_name}' not found")
            sys.exit(1)

        outputs = stacks[0].get("Outputs", [])
        memory_output = next((o for o in outputs if o["OutputKey"] == "AgentCoreMemoryId"), None)

        if not memory_output:
            print(f"Error: AgentCoreMemoryId output not found in stack '{stack_name}'")
            sys.exit(1)

        memory_id = memory_output["OutputValue"]
        print(f"Found Memory ID: {memory_id}")
        return memory_id

    except ClientError as e:
        print(f"Error accessing CloudFormation: {e}")
        sys.exit(1)


def get_agent_runtime_arn_from_stack(stack_name: str = "VirtualAssistantStack") -> str:
    """
    Get the AgentCore Runtime ARN from CloudFormation stack outputs.

    Args:
        stack_name: Name of the CloudFormation stack

    Returns:
        Agent Runtime ARN string

    Raises:
        SystemExit: If stack or output not found
    """
    cfn = boto3.client("cloudformation")

    try:
        response = cfn.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])

        if not stacks:
            print(f"Error: Stack '{stack_name}' not found")
            sys.exit(1)

        outputs = stacks[0].get("Outputs", [])
        runtime_output = next((o for o in outputs if o["OutputKey"] == "AgentCoreRuntimeArn"), None)

        if not runtime_output:
            print(f"Error: AgentCoreRuntimeArn output not found in stack '{stack_name}'")
            sys.exit(1)

        arn = runtime_output["OutputValue"]
        print(f"Found Agent Runtime ARN: {arn}")
        return arn

    except ClientError as e:
        print(f"Error accessing CloudFormation: {e}")
        sys.exit(1)


def create_agentcore_client():
    """
    Create bedrock-agentcore client with retry configuration.

    Returns:
        Configured boto3 client
    """
    config = Config(
        retries={
            "max_attempts": 100,
            "mode": "adaptive",  # Adaptive mode adjusts retry behavior based on response
        }
    )
    return boto3.client("bedrock-agentcore", config=config)


async def get_all_actors_async(memory_id: str) -> List[str]:
    """
    Get all actor IDs from AgentCore Memory asynchronously.

    Args:
        memory_id: The Memory ID

    Returns:
        List of actor IDs
    """
    client = create_agentcore_client()

    try:
        # Run the synchronous boto3 call in an executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: client.list_actors(memoryId=memory_id)
        )
        actors = [actor["actorId"] for actor in response.get("actorSummaries", [])]
        print(f"Found {len(actors)} actors")
        return actors

    except ClientError as e:
        print(f"Error listing actors: {e}")
        return []


async def delete_events_for_session(
    memory_id: str,
    actor_id: str,
    session_id: str,
    dry_run: bool = False,
    semaphore: asyncio.Semaphore = None,
) -> int:
    """
    Delete all events for a specific session asynchronously.

    Args:
        memory_id: The Memory ID
        actor_id: The actor ID
        session_id: The session ID
        dry_run: If True, only show what would be deleted
        semaphore: Semaphore for rate limiting

    Returns:
        Number of events deleted
    """
    client = create_agentcore_client()
    deleted_count = 0

    try:
        # List all events for this session
        response = client.list_events(
            memoryId=memory_id, actorId=actor_id, sessionId=session_id, maxResults=100
        )

        events = response.get("events", [])

        if not events:
            return 0

        # Delete events asynchronously with rate limiting
        tasks = []
        for event in events:
            event_id = event["eventId"]
            if dry_run:
                print(f"      [DRY RUN] Would delete event: {event_id}")
                deleted_count += 1
            else:
                # Create async task for deletion with semaphore
                task = asyncio.create_task(
                    delete_event_async(
                        client, memory_id, actor_id, session_id, event_id, semaphore
                    )
                )
                tasks.append(task)

        if tasks:
            # Wait for all deletions to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            deleted_count = sum(1 for r in results if r is True)

        return deleted_count

    except ClientError as e:
        print(f"    Error listing events for session {session_id}: {e}")
        return 0


async def delete_event_async(
    client,
    memory_id: str,
    actor_id: str,
    session_id: str,
    event_id: str,
    semaphore: asyncio.Semaphore = None,
) -> bool:
    """
    Delete a single event asynchronously with rate limiting.

    Boto3 handles retries automatically with adaptive retry mode.

    Args:
        client: Boto3 bedrock-agentcore client
        memory_id: The Memory ID
        actor_id: The actor ID
        session_id: The session ID
        event_id: The event ID
        semaphore: Semaphore for rate limiting

    Returns:
        True if successful, False otherwise
    """
    # Use semaphore to limit concurrent deletions
    async with semaphore if semaphore else asyncio.Semaphore(1):
        try:
            # Run the synchronous boto3 call in an executor
            # Boto3 will handle retries with exponential backoff automatically
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.delete_event(
                    memoryId=memory_id,
                    actorId=actor_id,
                    sessionId=session_id,
                    eventId=event_id,
                ),
            )
            return True
        except ClientError as e:
            print(f"      Error deleting event {event_id}: {e}")
            return False


async def stop_runtime_session_async(
    agent_runtime_arn: str,
    session_id: str,
    dry_run: bool = False,
    semaphore: asyncio.Semaphore = None,
) -> bool:
    """
    Stop an AgentCore Runtime session, failing gracefully if not running.

    Args:
        agent_runtime_arn: The Agent Runtime ARN
        session_id: The runtime session ID to stop
        dry_run: If True, only show what would be stopped
        semaphore: Semaphore for rate limiting

    Returns:
        True if stopped (or already stopped), False on unexpected error
    """
    if dry_run:
        print(f"      [DRY RUN] Would stop runtime session: {session_id}")
        return True

    async with semaphore if semaphore else asyncio.Semaphore(1):
        client = create_agentcore_client()
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.stop_runtime_session(
                    agentRuntimeArn=agent_runtime_arn,
                    runtimeSessionId=session_id,
                ),
            )
            print(f"      Stopped runtime session: {session_id}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            # Gracefully handle sessions that aren't running
            if error_code in ("ResourceNotFoundException", "ValidationException", "ConflictException"):
                print(f"      Session {session_id} not running (skipped): {error_code}")
                return True
            print(f"      Error stopping session {session_id}: {e}")
            return False


async def process_actor(
    memory_id: str,
    actor_id: str,
    dry_run: bool = False,
    semaphore: asyncio.Semaphore = None,
    agent_runtime_arn: str = None,
) -> int:
    """
    Process all sessions for an actor asynchronously.

    Args:
        memory_id: The Memory ID
        actor_id: The actor ID
        dry_run: If True, only show what would be deleted
        semaphore: Semaphore for rate limiting
        agent_runtime_arn: If provided, stop runtime sessions before clearing events

    Returns:
        Total number of events deleted for this actor
    """
    client = create_agentcore_client()
    total_deleted = 0

    print(f"  Processing actor: {actor_id}")

    try:
        # List all sessions for this actor
        response = client.list_sessions(memoryId=memory_id, actorId=actor_id)
        sessions = response.get("sessionSummaries", [])

        if not sessions:
            print(f"    No sessions found for actor {actor_id}")
            return 0

        print(f"    Found {len(sessions)} sessions")

        # Stop runtime sessions first if requested
        if agent_runtime_arn:
            print(f"    Stopping runtime sessions for actor {actor_id}...")
            stop_tasks = []
            for session in sessions:
                session_id = session["sessionId"]
                task = asyncio.create_task(
                    stop_runtime_session_async(agent_runtime_arn, session_id, dry_run, semaphore)
                )
                stop_tasks.append(task)
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Process all sessions concurrently
        tasks = []
        for session in sessions:
            session_id = session["sessionId"]
            task = asyncio.create_task(
                delete_events_for_session(
                    memory_id, actor_id, session_id, dry_run, semaphore
                )
            )
            tasks.append((session_id, task))

        # Wait for all sessions to be processed
        for session_id, task in tasks:
            deleted_count = await task
            if deleted_count > 0:
                action = "Would delete" if dry_run else "Deleted"
                print(f"    Session {session_id}: {action} {deleted_count} events")
                total_deleted += deleted_count

        return total_deleted

    except ClientError as e:
        print(f"  Error listing sessions for actor {actor_id}: {e}")
        return 0


async def clear_memory_async(
    memory_id: str,
    actor_ids: List[str],
    dry_run: bool = False,
    max_concurrent: int = 10,
    agent_runtime_arn: str = None,
) -> None:
    """
    Clear memory events for multiple actors asynchronously.

    Args:
        memory_id: The Memory ID
        actor_ids: List of actor IDs to process
        dry_run: If True, only show what would be deleted
        max_concurrent: Maximum number of concurrent delete operations
        agent_runtime_arn: If provided, stop runtime sessions before clearing events
    """
    print(f"\nProcessing {len(actor_ids)} actors...")
    print(f"Rate limit: {max_concurrent} concurrent deletions")
    if agent_runtime_arn:
        print(f"Will stop runtime sessions using ARN: {agent_runtime_arn}")

    # Create semaphore to limit concurrent deletions
    semaphore = asyncio.Semaphore(max_concurrent)

    # Process all actors concurrently
    tasks = [
        asyncio.create_task(
            process_actor(memory_id, actor_id, dry_run, semaphore, agent_runtime_arn)
        )
        for actor_id in actor_ids
    ]

    # Wait for all actors to be processed
    results = await asyncio.gather(*tasks)

    total_deleted = sum(results)
    action = "Would delete" if dry_run else "Deleted"
    print(f"\n{action} {total_deleted} total events across {len(actor_ids)} actors")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clear AgentCore Memory events for Virtual Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clear all actors (auto-detect memory ID from stack)
  uv run scripts/clear_memory.py --all-actors

  # Clear specific actors (user IDs)
  uv run scripts/clear_memory.py user123 user456

  # Specify memory ID directly
  uv run scripts/clear_memory.py --memory-id mem-abc123 --all-actors

  # Limit concurrent deletions to avoid rate limits
  uv run scripts/clear_memory.py --all-actors --max-concurrent 5

  # Specify custom stack name
  uv run scripts/clear_memory.py --stack-name MyStack --all-actors

  # Dry run (show what would be deleted)
  uv run scripts/clear_memory.py --all-actors --dry-run

  # Also stop runtime sessions found in memory
  uv run scripts/clear_memory.py --all-actors --stop-sessions

  # Stop sessions with explicit runtime ARN
  uv run scripts/clear_memory.py --all-actors --stop-sessions --agent-runtime-arn arn:aws:bedrock:...
        """,
    )

    parser.add_argument(
        "--memory-id",
        help="Memory ID (if not provided, looks up from CloudFormation stack)",
    )
    parser.add_argument(
        "--stack-name",
        default="VirtualAssistantStack",
        help="CloudFormation stack name (default: VirtualAssistantStack, ignored if --memory-id provided)",
    )
    parser.add_argument(
        "--all-actors", action="store_true", help="Clear memory for all actors"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum number of concurrent delete operations (default: 10)",
    )
    parser.add_argument(
        "--stop-sessions",
        action="store_true",
        help="Stop AgentCore Runtime sessions before clearing memory events",
    )
    parser.add_argument(
        "--agent-runtime-arn",
        help="Agent Runtime ARN (if not provided, looks up from CloudFormation stack; requires --stop-sessions)",
    )
    parser.add_argument(
        "actors", nargs="*", help="Specific actor IDs (user IDs) to clear"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all_actors and not args.actors:
        parser.error("Must specify either --all-actors or provide actor IDs")

    # Get Memory ID - either from argument or CloudFormation stack
    if args.memory_id:
        memory_id = args.memory_id
        print(f"Using provided Memory ID: {memory_id}")
    else:
        memory_id = get_memory_id_from_stack(args.stack_name)

    # Get Agent Runtime ARN if stopping sessions
    agent_runtime_arn = None
    if args.stop_sessions:
        if args.agent_runtime_arn:
            agent_runtime_arn = args.agent_runtime_arn
            print(f"Using provided Agent Runtime ARN: {agent_runtime_arn}")
        else:
            agent_runtime_arn = get_agent_runtime_arn_from_stack(args.stack_name)

    # Get actor IDs and run clearing
    async def run():
        if args.all_actors:
            actor_ids = await get_all_actors_async(memory_id)
            if not actor_ids:
                print("No actors found")
                return
        else:
            actor_ids = args.actors

        # Run async clearing
        if args.dry_run:
            print("\n*** DRY RUN MODE - No events will be deleted ***\n")

        await clear_memory_async(
            memory_id, actor_ids, args.dry_run, args.max_concurrent, agent_runtime_arn
        )

    asyncio.run(run())

    print("\nMemory clearing complete!")


if __name__ == "__main__":
    main()
