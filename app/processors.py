from ckan_client import search_packages, get_package, deduplicate_packages
from s3_utils import upload_url_to_s3
from utils import (
    safe_name,
    get_filename,
    get_resource_format,
    resource_matches,
    is_allowed_resource,
    extract_web_uu_year
)


def select_packages(dataset: dict, packages: list[dict]) -> list[dict]:
    if not packages:
        return []

    if dataset.get("pick_latest"):
        return sorted(
            packages,
            key=lambda p: p.get("metadata_modified") or "",
            reverse=True
        )[:1]

    return packages


def build_s3_key(
    dataset: dict,
    package_name: str,
    filename: str,
    snapshot_date: str
) -> str:
    s3_prefix = dataset["s3_prefix"]
    dataset_type = dataset.get("type", "standard")

    web_uu_year = extract_web_uu_year(filename)

    if dataset_type == "mfinante_uu_years" and web_uu_year:
        file_ext = filename.rsplit(".", 1)[-1].lower()
        canonical_filename = f"web_uu_an{web_uu_year}.{file_ext}"

        return (
            f"{s3_prefix}/"
            f"source_year={web_uu_year}/"
            f"snapshot_date={snapshot_date}/"
            f"{canonical_filename}"
        )

    return (
        f"{s3_prefix}/"
        f"snapshot_date={snapshot_date}/"
        f"package={safe_name(package_name)}/"
        f"{filename}"
    )


def process_package_resources(
    dataset: dict,
    package: dict,
    bucket: str,
    snapshot_date: str,
    include_patterns: list[str] | None = None
) -> list[str]:
    processed = []

    package_id = package.get("id")
    package_name = package.get("name")
    package_title = package.get("title")

    if "resources" in package:
        full_package = package
    else:
        full_package = get_package(package_id)

    resources = full_package.get("resources", [])

    if not resources:
        print("    No resources found.")
        return processed

    dataset_name = dataset["name"]
    dataset_query = dataset.get("query", "")

    include_patterns = include_patterns or dataset.get("include_resource_regex", [])

    for resource in resources:
        resource_url = resource.get("url")

        if not resource_url:
            continue

        filename = get_filename(resource)
        resource_format = get_resource_format(resource, filename)

        if not is_allowed_resource(resource, filename):
            print(
                f"    Skipping unsupported format: "
                f"{resource_format} / {filename}"
            )
            continue

        if not resource_matches(filename, include_patterns):
            print(f"    Skipping not matching include patterns: {filename}")
            continue

        s3_key = build_s3_key(
            dataset=dataset,
            package_name=package_name,
            filename=filename,
            snapshot_date=snapshot_date
        )

        print(f"    Processing {filename}")
        print(f"      Source: {resource_url}")
        print(f"      Target: s3://{bucket}/{s3_key}")

        status = upload_url_to_s3(
            resource_url=resource_url,
            bucket=bucket,
            key=s3_key,
            metadata={
                "source": "data.gov.ro",
                "dataset_name": dataset_name,
                "dataset_query": dataset_query,
                "package_id": package_id,
                "package_name": package_name,
                "package_title": package_title,
                "resource_id": resource.get("id"),
                "resource_name": resource.get("name"),
                "resource_format": resource_format,
                "source_url": resource_url,
                "snapshot_date": snapshot_date
            }
        )

        processed.append(f"{status}: s3://{bucket}/{s3_key}")

    return processed


def process_standard_dataset(
    dataset: dict,
    bucket: str,
    snapshot_date: str
) -> list[str]:
    processed = []

    dataset_name = dataset["name"]

    print(f"\nProcessing standard dataset: {dataset_name}")

    try:
        if dataset.get("package_id"):
            print(f"  Loading exact package: {dataset['package_id']}")
            packages = [get_package(dataset["package_id"])]

        else:
            dataset_query = dataset["query"]
            rows = dataset.get("rows", 3)

            print(f"  Searching dataset: {dataset_name} / {dataset_query}")

            packages = search_packages(dataset_query, rows=rows)
            packages = select_packages(dataset, packages)

    except Exception as exc:
        print(f"  Failed to load packages for dataset {dataset_name}: {exc}")
        return processed

    if not packages:
        print("  No packages found.")
        return processed

    for package in packages:
        package_title = package.get("title")
        package_name = package.get("name")

        print(f"  Selected package: {package_title} ({package_name})")

        try:
            processed.extend(
                process_package_resources(
                    dataset=dataset,
                    package=package,
                    bucket=bucket,
                    snapshot_date=snapshot_date
                )
            )

        except Exception as exc:
            print(f"  Failed to process package {package_name}: {exc}")

    return processed


def build_mfinante_search_queries(year: int) -> list[str]:
    return [
        f"web_uu_an{year}",
        f"WEB_UU_AN{year}",
        f"situatii financiare {year}",
        f"situații financiare {year}"
    ]


def process_mfinante_uu_years(
    dataset: dict,
    bucket: str,
    snapshot_date: str
) -> list[str]:
    processed = []

    start_year = int(dataset["start_year"])
    end_year = int(dataset["end_year"])
    rows = int(dataset.get("rows", 20))
    package_ids_by_year = dataset.get("package_ids_by_year", {})

    print(
        f"\nProcessing MFinante WEB_UU years: "
        f"{start_year} - {end_year}"
    )

    for year in range(start_year, end_year + 1):
        print(f"\n  Looking for WEB_UU files for year {year}")

        include_patterns = [
            rf"^(web_uu_an|webuuan|webuu|web_uu_){year}\.(txt|csv)$"
        ]

        packages = []

        exact_package_id = package_ids_by_year.get(str(year))

        if exact_package_id:
            print(f"  Using configured package id for {year}: {exact_package_id}")

            try:
                packages.append(get_package(exact_package_id))
            except Exception as exc:
                print(f"  Exact package failed for {year}: {exc}")

        for query in build_mfinante_search_queries(year):
            print(f"  Searching CKAN: {query}")

            try:
                search_results = search_packages(query, rows=rows)
                packages.extend(search_results)

            except Exception as exc:
                print(f"  Search failed for query '{query}': {exc}")

        packages = deduplicate_packages(packages)

        if not packages:
            print(f"  No packages found for {year}.")
            continue

        year_processed = []

        for package in packages:
            package_title = package.get("title")
            package_name = package.get("name")

            print(f"  Checking package: {package_title} ({package_name})")

            try:
                package_processed = process_package_resources(
                    dataset=dataset,
                    package=package,
                    bucket=bucket,
                    snapshot_date=snapshot_date,
                    include_patterns=include_patterns
                )

            except Exception as exc:
                print(f"  Failed to process package {package_name}: {exc}")
                continue

            year_processed.extend(package_processed)

            found_txt = any(f"web_uu_an{year}.txt" in p.lower() for p in year_processed)
            found_csv = any(f"web_uu_an{year}.csv" in p.lower() for p in year_processed)

            if found_txt and found_csv:
                print(f"  Found both TXT and CSV for {year}.")
                break

        if not year_processed:
            print(f"  No WEB_UU files downloaded/found for {year}.")

        processed.extend(year_processed)

    return processed