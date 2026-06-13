import json
import os
from datetime import datetime, timezone

from processors import (
    process_standard_dataset,
    process_mfinante_uu_years
)

from s3_utils import AWS_REGION


def main():
    bucket = os.environ.get("S3_BUCKET")

    if not bucket:
        raise RuntimeError(
            "Missing S3_BUCKET environment variable. "
            "Example PowerShell: $env:S3_BUCKET='ro-company-lake'"
        )

    config_path = os.environ.get("CONFIG_PATH", "config/datasets.json")
    snapshot_date = datetime.now(timezone.utc).date().isoformat()

    print(f"Using AWS region: {AWS_REGION}")
    print(f"Using S3 bucket: {bucket}")
    print(f"Using config file: {config_path}")
    print(f"Snapshot date: {snapshot_date}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    processed = []

    for dataset in config["datasets"]:
        dataset_type = dataset.get("type", "standard")

        if dataset_type == "mfinante_uu_years":
            processed.extend(
                process_mfinante_uu_years(
                    dataset=dataset,
                    bucket=bucket,
                    snapshot_date=snapshot_date
                )
            )

        else:
            processed.extend(
                process_standard_dataset(
                    dataset=dataset,
                    bucket=bucket,
                    snapshot_date=snapshot_date
                )
            )

    print("\nProcessed files:")
    for item in processed:
        print(item)

    print(f"\nTotal processed/skipped files: {len(processed)}")


if __name__ == "__main__":
    main()