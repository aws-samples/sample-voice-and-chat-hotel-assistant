#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel Knowledge Base Document Upload and Ingestion Script

This script uploads all hotel documents and metadata files to S3 and triggers
Knowledge Base ingestion. It monitors the ingestion progress and validates completion.

Usage:
    python hotel_data/scripts/upload_and_ingest_documents.py [--stack-name STACK_NAME] [--dry-run]

Requirements:
    - AWS CLI configured with appropriate permissions
    - Hotel PMS API Stack deployed with Knowledge Base
    - Hotel documents and metadata files generated

The script will:
1. Get S3 bucket name and Knowledge Base ID from CloudFormation outputs
2. Upload all documents and metadata files to S3 with proper structure
3. Trigger Knowledge Base data source sync
4. Monitor ingestion progress and validate completion
"""

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError as e:
    print("❌ Missing required AWS SDK packages.")
    print("Please install boto3: pip install boto3")
    print(f"Import error: {e}")
    sys.exit(1)


class DocumentUploadError(Exception):
    """Custom exception for document upload errors."""

    pass


class IngestionError(Exception):
    """Custom exception for ingestion errors."""

    pass


class HotelDocumentUploader:
    """
    Handles uploading hotel documents to S3 and triggering Knowledge Base ingestion.
    """

    def __init__(
        self,
        stack_name: str = "HotelPmsStack",
        dry_run: bool = False,
        force_upload: bool = False,
    ):
        """
        Initialize the uploader.

        Args:
            stack_name: CloudFormation stack name containing the Knowledge Base
            dry_run: If True, only show what would be uploaded without actually doing it
            force_upload: If True, upload all files regardless of changes
        """
        self.stack_name = stack_name
        self.dry_run = dry_run
        self.force_upload = force_upload

        # Initialize AWS clients
        try:
            self.cloudformation = boto3.client("cloudformation")
            self.s3 = boto3.client("s3")
            self.bedrock_agent = boto3.client("bedrock-agent")
        except NoCredentialsError:
            raise DocumentUploadError(
                "AWS credentials not configured. Please run 'aws configure' or set environment variables."
            )

        # Get infrastructure details from CloudFormation
        self._get_infrastructure_details()

        # Set up paths
        script_dir = Path(__file__).parent
        self.source_path = script_dir.parent / "hotel-knowledge-base"

        if not self.source_path.exists():
            raise DocumentUploadError(f"Source path does not exist: {self.source_path}")

    def _get_infrastructure_details(self):
        """Get S3 bucket name and Knowledge Base details from CloudFormation outputs."""
        try:
            response = self.cloudformation.describe_stacks(StackName=self.stack_name)
            stack = response["Stacks"][0]

            if stack["StackStatus"] not in [
                "CREATE_COMPLETE",
                "UPDATE_COMPLETE",
                "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
            ]:
                raise DocumentUploadError(
                    f"Stack {self.stack_name} is not in a complete state. "
                    f"Current status: {stack['StackStatus']}. "
                    f"Please ensure the stack is deployed successfully before running this script."
                )

            outputs = {
                output["OutputKey"]: output["OutputValue"]
                for output in stack.get("Outputs", [])
            }

            # Get required outputs - these should match the output names from the CDK construct
            self.bucket_name = outputs.get("HotelDocumentsBucketName")
            self.knowledge_base_id = outputs.get("HotelKnowledgeBaseId")
            self.data_source_id = outputs.get("HotelDataSourceId")

            # Alternative output names to check (in case naming differs)
            if not self.bucket_name:
                self.bucket_name = outputs.get("DocumentsBucketName")
            if not self.knowledge_base_id:
                self.knowledge_base_id = outputs.get("KnowledgeBaseId")
            if not self.data_source_id:
                self.data_source_id = outputs.get("DataSourceId")

            # Show available outputs for debugging
            if not all([self.bucket_name, self.knowledge_base_id, self.data_source_id]):
                print("Available CloudFormation outputs:")
                for key, value in outputs.items():
                    print(f"  {key}: {value}")
                print()

            if not self.bucket_name:
                raise DocumentUploadError(
                    "Could not find S3 bucket name in stack outputs. "
                    "Expected: HotelDocumentsBucketName or DocumentsBucketName"
                )

            if not self.knowledge_base_id:
                raise DocumentUploadError(
                    "Could not find Knowledge Base ID in stack outputs. "
                    "Expected: HotelKnowledgeBaseId or KnowledgeBaseId"
                )

            if not self.data_source_id:
                raise DocumentUploadError(
                    "Could not find Data Source ID in stack outputs. "
                    "Expected: HotelDataSourceId or DataSourceId"
                )

            print("✓ Found infrastructure:")
            print(f"  S3 Bucket: {self.bucket_name}")
            print(f"  Knowledge Base ID: {self.knowledge_base_id}")
            print(f"  Data Source ID: {self.data_source_id}")
            print()

        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationError":
                raise DocumentUploadError(f"Stack {self.stack_name} does not exist")
            else:
                raise DocumentUploadError(f"Error accessing CloudFormation: {e}")

    def _get_hotel_files(self) -> List[Tuple[Path, str]]:
        """
        Get all hotel documents and metadata files to upload.

        Returns:
            List of tuples (local_file_path, s3_key)
        """
        files_to_upload = []

        for hotel_dir in self.source_path.iterdir():
            if not hotel_dir.is_dir() or hotel_dir.name.startswith("."):
                continue

            hotel_name = hotel_dir.name

            for file_path in hotel_dir.iterdir():
                if not file_path.is_file():
                    continue

                filename = file_path.name

                # Skip README files and .DS_Store
                if filename.lower() == "readme.md" or filename == ".DS_Store":
                    continue

                # Include .md files and .metadata.json files
                if filename.endswith(".md") or filename.endswith(".metadata.json"):
                    s3_key = f"knowledge-base/{hotel_name}/{filename}"
                    files_to_upload.append((file_path, s3_key))

        return files_to_upload

    def _file_needs_upload(self, local_path: Path, s3_key: str) -> bool:
        """
        Check if a file needs to be uploaded by comparing timestamps.

        Args:
            local_path: Local file path
            s3_key: S3 object key

        Returns:
            True if file needs to be uploaded, False otherwise
        """
        if self.force_upload:
            return True

        try:
            # Get S3 object metadata
            response = self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            s3_last_modified = response["LastModified"]

            # Get local file modification time
            local_mtime = datetime.fromtimestamp(
                local_path.stat().st_mtime, tz=timezone.utc
            )

            # Compare timestamps - upload if local file is newer
            # Add a small buffer (1 second) to account for timestamp precision differences
            return local_mtime > (s3_last_modified + timedelta(seconds=1))

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # File doesn't exist in S3, needs upload
                return True
            else:
                # Error checking S3, assume needs upload
                print(f"  ⚠️  Error checking S3 for {s3_key}: {e}")
                return True
        except Exception as e:
            # Unexpected error, assume needs upload
            print(f"  ⚠️  Unexpected error checking {s3_key}: {e}")
            return True

    def _upload_file(self, local_path: Path, s3_key: str) -> bool:
        """
        Upload a single file to S3.

        Args:
            local_path: Local file path
            s3_key: S3 object key

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                print(
                    f"  [DRY RUN] Would upload: {local_path} -> s3://{self.bucket_name}/{s3_key}"
                )
                return True

            # Determine content type
            content_type = (
                "text/markdown" if s3_key.endswith(".md") else "application/json"
            )

            # Upload file
            with open(local_path, "rb") as f:
                self.s3.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=f,
                    ContentType=content_type,
                    ServerSideEncryption="AES256",
                )

            print(f"  ✓ Uploaded: {s3_key}")
            return True

        except ClientError as e:
            print(f"  ✗ Failed to upload {s3_key}: {e}")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error uploading {s3_key}: {e}")
            return False

    def upload_documents(self) -> Dict[str, int]:
        """
        Upload all hotel documents and metadata files to S3.

        Returns:
            Dictionary with upload statistics
        """
        print("Uploading hotel documents to S3...")
        print("=" * 50)

        files_to_upload = self._get_hotel_files()

        if not files_to_upload:
            raise DocumentUploadError("No files found to upload")

        print(f"Found {len(files_to_upload)} files to upload")
        print()

        stats = {
            "total_files": len(files_to_upload),
            "successful_uploads": 0,
            "failed_uploads": 0,
            "skipped_files": 0,
            "hotels_processed": set(),
            "document_types": set(),
            "metadata_files": 0,
        }

        # Group files by hotel for organized output
        files_by_hotel = {}
        for local_path, s3_key in files_to_upload:
            hotel_name = s3_key.split("/")[1]  # Extract hotel name from s3_key
            if hotel_name not in files_by_hotel:
                files_by_hotel[hotel_name] = []
            files_by_hotel[hotel_name].append((local_path, s3_key))

        # Upload files hotel by hotel
        for hotel_name, hotel_files in files_by_hotel.items():
            print(f"Processing hotel: {hotel_name}")
            stats["hotels_processed"].add(hotel_name)

            hotel_uploads = 0
            hotel_skipped = 0

            for local_path, s3_key in hotel_files:
                # Check if file needs upload
                if not self._file_needs_upload(local_path, s3_key):
                    if not self.dry_run:
                        print(f"  ⏭️  Skipped (unchanged): {s3_key}")
                    else:
                        print(
                            f"  [DRY RUN] Would skip (unchanged): {local_path} -> s3://{self.bucket_name}/{s3_key}"
                        )
                    hotel_skipped += 1
                    stats["successful_uploads"] += (
                        1  # Count as successful since it's up to date
                    )

                    # Track file types
                    if s3_key.endswith(".metadata.json"):
                        stats["metadata_files"] += 1
                    elif s3_key.endswith(".md"):
                        filename = local_path.name.replace(".md", "")
                        stats["document_types"].add(filename)
                    continue

                # Upload the file
                if self._upload_file(local_path, s3_key):
                    stats["successful_uploads"] += 1
                    hotel_uploads += 1

                    # Track file types
                    if s3_key.endswith(".metadata.json"):
                        stats["metadata_files"] += 1
                    elif s3_key.endswith(".md"):
                        # Extract document type from filename
                        filename = local_path.name.replace(".md", "")
                        stats["document_types"].add(filename)
                else:
                    stats["failed_uploads"] += 1

            if hotel_uploads > 0 or hotel_skipped > 0:
                print(
                    f"  Hotel {hotel_name}: {hotel_uploads} uploaded, {hotel_skipped} skipped"
                )
            print()

        # Convert sets to counts for final stats
        stats["hotels_processed"] = len(stats["hotels_processed"])
        stats["document_types"] = len(stats["document_types"])

        return stats

    def trigger_ingestion(self) -> str:
        """
        Trigger Knowledge Base data source ingestion.

        Returns:
            Ingestion job ID
        """
        if self.dry_run:
            print("[DRY RUN] Would trigger Knowledge Base ingestion")
            return "dry-run-job-id"

        try:
            print("Triggering Knowledge Base ingestion...")

            response = self.bedrock_agent.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                description="Hotel documents ingestion triggered by upload script",
            )

            job_id = response["ingestionJob"]["ingestionJobId"]
            print(f"✓ Ingestion job started: {job_id}")
            return job_id

        except ClientError as e:
            raise IngestionError(f"Failed to start ingestion job: {e}")

    def monitor_ingestion(self, job_id: str, timeout_minutes: int = 30) -> bool:
        """
        Monitor ingestion progress until completion or timeout.

        Args:
            job_id: Ingestion job ID
            timeout_minutes: Maximum time to wait for completion

        Returns:
            True if ingestion completed successfully, False otherwise
        """
        if self.dry_run:
            print(f"[DRY RUN] Would monitor ingestion job: {job_id}")
            return True

        print(f"Monitoring ingestion job: {job_id}")
        print("This may take several minutes...")
        print()

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while True:
            try:
                response = self.bedrock_agent.get_ingestion_job(
                    knowledgeBaseId=self.knowledge_base_id,
                    dataSourceId=self.data_source_id,
                    ingestionJobId=job_id,
                )

                job = response["ingestionJob"]
                status = job["status"]

                # Print status update
                elapsed_minutes = (time.time() - start_time) / 60
                print(f"[{elapsed_minutes:.1f}m] Status: {status}")

                if status == "COMPLETE":
                    print("✓ Ingestion completed successfully!")

                    # Print ingestion statistics if available
                    if "statistics" in job:
                        stats = job["statistics"]
                        print(
                            f"  Documents processed: {stats.get('numberOfDocumentsScanned', 'N/A')}"
                        )
                        print(
                            f"  Documents indexed: {stats.get('numberOfNewDocumentsIndexed', 'N/A')}"
                        )
                        print(
                            f"  Documents updated: {stats.get('numberOfModifiedDocumentsIndexed', 'N/A')}"
                        )
                        print(
                            f"  Documents deleted: {stats.get('numberOfDocumentsDeleted', 'N/A')}"
                        )

                    return True

                elif status == "FAILED":
                    print("✗ Ingestion failed!")
                    if "failureReasons" in job:
                        for reason in job["failureReasons"]:
                            print(f"  Error: {reason}")
                    return False

                elif status in ["STARTING", "IN_PROGRESS"]:
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        print(f"✗ Ingestion timed out after {timeout_minutes} minutes")
                        return False

                    # Wait before next check
                    time.sleep(  # nosemgrep: arbitrary-sleep - Check every 30 seconds
                        30
                    )

                else:
                    print(f"✗ Unexpected ingestion status: {status}")
                    return False

            except ClientError as e:
                print(f"✗ Error checking ingestion status: {e}")
                return False
            except KeyboardInterrupt:
                print("\n⚠️  Monitoring interrupted by user")
                print(f"Ingestion job {job_id} may still be running")
                return False

    def validate_upload(self) -> bool:
        """
        Validate that all expected files were uploaded to S3.

        Returns:
            True if validation passes, False otherwise
        """
        if self.dry_run:
            print("[DRY RUN] Would validate uploaded files")
            return True

        print("Validating uploaded files...")

        try:
            # List all objects in the knowledge-base prefix
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix="knowledge-base/"
            )

            if "Contents" not in response:
                print("✗ No files found in S3 bucket")
                return False

            uploaded_files = {obj["Key"] for obj in response["Contents"]}
            expected_files = {s3_key for _, s3_key in self._get_hotel_files()}

            missing_files = expected_files - uploaded_files
            extra_files = uploaded_files - expected_files

            if missing_files:
                print(f"✗ Missing files ({len(missing_files)}):")
                for file in sorted(missing_files):
                    print(f"  - {file}")

            if extra_files:
                print(f"ℹ️  Extra files ({len(extra_files)}):")
                for file in sorted(extra_files):
                    print(f"  + {file}")

            if not missing_files:
                print(f"✓ All {len(expected_files)} expected files are present in S3")
                return True
            else:
                return False

        except ClientError as e:
            print(f"✗ Error validating uploads: {e}")
            return False

    def run(self) -> bool:
        """
        Run the complete upload and ingestion process.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Upload documents
            upload_stats = self.upload_documents()

            print("Upload Summary:")
            print("=" * 50)
            print(f"Total files: {upload_stats['total_files']}")
            print(f"Successful uploads: {upload_stats['successful_uploads']}")
            print(f"Failed uploads: {upload_stats['failed_uploads']}")
            print(f"Hotels processed: {upload_stats['hotels_processed']}")
            print(f"Document types: {upload_stats['document_types']}")
            print(f"Metadata files: {upload_stats['metadata_files']}")

            # Show incremental upload info
            if "skipped_files" in upload_stats and upload_stats["skipped_files"] > 0:
                print(f"Files skipped (unchanged): {upload_stats['skipped_files']}")
                print(
                    f"Files actually uploaded: {upload_stats['successful_uploads'] - upload_stats['skipped_files']}"
                )
            print()

            if upload_stats["failed_uploads"] > 0:
                print(
                    "⚠️  Some files failed to upload. Check the output above for details."
                )
                return False

            # Step 2: Validate upload
            if not self.validate_upload():
                print("✗ Upload validation failed")
                return False

            print()

            # Step 3: Trigger ingestion
            job_id = self.trigger_ingestion()
            print()

            # Step 4: Monitor ingestion
            if not self.monitor_ingestion(job_id):
                print("✗ Ingestion failed or timed out")
                return False

            print()
            print("🎉 Document upload and ingestion completed successfully!")
            print()
            print("Next steps:")
            print("- Test Knowledge Base queries through the AgentCore Gateway")
            print("- Verify hotel-specific filtering is working correctly")
            print("- Check CloudWatch logs for any issues")

            return True

        except (DocumentUploadError, IngestionError) as e:
            print(f"✗ Error: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False


def main():
    """Main function to run the upload and ingestion script."""
    parser = argparse.ArgumentParser(
        description="Upload hotel documents to S3 and trigger Knowledge Base ingestion"
    )
    parser.add_argument(
        "--stack-name",
        default="HotelPmsStack",
        help="CloudFormation stack name (default: HotelPmsStack)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )
    parser.add_argument(
        "--force-upload",
        action="store_true",
        help="Upload all files regardless of changes",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Ingestion timeout in minutes (default: 30)",
    )

    args = parser.parse_args()

    print("Hotel Knowledge Base Document Upload and Ingestion")
    print("=" * 60)
    print()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No actual changes will be made")
        print()

    try:
        uploader = HotelDocumentUploader(
            stack_name=args.stack_name,
            dry_run=args.dry_run,
            force_upload=args.force_upload,
        )

        success = uploader.run()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⚠️  Operation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
