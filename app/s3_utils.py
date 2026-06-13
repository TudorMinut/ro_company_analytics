import os
import time
import tempfile
import http.client
import urllib.error
import urllib.parse
import urllib.request
from pathlib import PurePosixPath

import boto3
import botocore
import certifi

from utils import safe_metadata_value, format_size


AWS_REGION = os.environ.get("AWS_REGION", "eu-central-1")


def create_s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        verify=certifi.where()
    )


def s3_object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True

    except botocore.exceptions.ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code in ["404", "NoSuchKey", "NotFound"]:
            return False

        raise


def download_url_to_temp_file(resource_url: str, max_retries: int = 5) -> str:
    last_error = None

    for attempt in range(1, max_retries + 1):
        temp_path = None

        try:
            request = urllib.request.Request(
                resource_url,
                headers={"User-Agent": "ro-company-analytics/1.0"}
            )

            with urllib.request.urlopen(request, timeout=900) as response:
                content_length = response.headers.get("Content-Length")

                if content_length:
                    remote_size = int(content_length)
                    print(f"      Remote file size: {format_size(remote_size)}")
                else:
                    print("      Remote file size: unknown")

                suffix = PurePosixPath(
                    urllib.parse.urlparse(resource_url).path
                ).suffix or ".dat"

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    temp_path = tmp.name
                    print(f"      Temp file: {temp_path}")

                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        tmp.write(chunk)

            local_size = os.path.getsize(temp_path)
            print(f"      Downloaded local size: {format_size(local_size)}")

            return temp_path

        except (
            http.client.IncompleteRead,
            urllib.error.URLError,
            TimeoutError,
            ConnectionError
        ) as exc:
            last_error = exc

            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            print(f"      Download failed, retry {attempt}/{max_retries}: {exc}")
            time.sleep(5 * attempt)

    raise RuntimeError(
        f"Failed to download after {max_retries} retries: {resource_url}"
    ) from last_error


def upload_url_to_s3(resource_url: str, bucket: str, key: str, metadata: dict) -> str:
    s3 = create_s3_client()

    if s3_object_exists(s3, bucket, key):
        print("      Already exists in S3, skipping.")
        return "skipped"

    clean_metadata = {
        k: safe_metadata_value(v)
        for k, v in metadata.items()
        if v is not None
    }

    temp_path = None

    try:
        temp_path = download_url_to_temp_file(resource_url)

        print("      Uploading temp file to S3...")

        s3.upload_file(
            Filename=temp_path,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "Metadata": clean_metadata
            }
        )

        print("      Upload complete.")
        return "uploaded"

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            print("      Temp file deleted.")