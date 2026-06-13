# Romanian Company Analytics Platform

Data platform for collecting Romanian company registry and financial datasets, storing raw files in AWS S3, transforming them in Databricks with a Bronze/Silver/Gold medallion model, and exposing analytics-ready tables to Power BI.

## Architecture

```text
data.gov.ro / ONRC / MFinante
        |
        v
Python downloader on AWS ECS Fargate
        |
        v
AWS S3 raw data lake
        |
        v
Databricks Unity Catalog external location
        |
        v
Bronze Delta tables
        |
        v
Silver cleaned relational model
        |
        v
Gold Power BI-ready analytics tables
        |
        v
Power BI dashboards
```

The repository currently contains the ingestion application, AWS helper infrastructure files, dataset configuration, and Databricks notebooks.

## Repository Layout

```text
.
+-- app/
|   +-- downloader.py       # Main ingestion entrypoint
|   +-- ckan_client.py      # data.gov.ro CKAN API client
|   +-- processors.py       # Dataset/resource selection and S3 key logic
|   +-- s3_utils.py         # Download-to-temp and upload-to-S3 utilities
|   +-- utils.py            # Filename, metadata, and matching helpers
+-- config/
|   +-- datasets.json       # Source dataset definitions
+-- infra/
|   +-- ecs-task-definition.json
|   +-- iam/                # IAM policy/trust-policy templates
+-- notebooks/
|   +-- 00_bronze_layer/
|   +-- 01_silver_layer/
|   +-- 02_gold_layer/
+-- Dockerfile
+-- requirements.txt
+-- architecture.drawio
```

## Source Data

Configured sources are defined in `config/datasets.json`.

Main datasets:

- ONRC company registry files, including `od_firme.csv`, `od_caen_autorizat.csv`, and `od_stare_firma.csv`.
- ONRC nomenclatures, including `n_caen.csv`, `n_stare_firma.csv`, and `n_versiune_caen.csv`.
- MFinante annual financial statement files named like `web_uu_anYYYY.txt` or `web_uu_anYYYY.csv`.
- MFinante taxpayer identification data.

The MFinante annual financial files are stored by actual source year:

```text
s3://ro-company-lake/raw_v2/mfinante/situatii_financiare_uu/
  source_year=2025/
    snapshot_date=YYYY-MM-DD/
      web_uu_an2025.csv
      web_uu_an2025.txt
```

This partitioning is important because older CKAN packages can contain mixed or inconsistent yearly resources.

## Local Ingestion Run

Prerequisites:

- Python 3.12
- AWS credentials with permission to write to the target S3 bucket
- Network access to `https://data.gov.ro`

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the downloader:

```powershell
$env:S3_BUCKET = "ro-company-lake"
$env:AWS_REGION = "eu-central-1"
$env:CONFIG_PATH = "config/datasets.json"
python app/downloader.py
```

The downloader:

- Reads dataset definitions from `config/datasets.json`.
- Searches or loads packages through the CKAN API.
- Filters resources by filename patterns.
- Downloads each source file to a temporary local file.
- Uploads the file to S3 with source metadata.
- Skips files that already exist at the target S3 key.

## AWS Deployment

Intended AWS components:

- ECR repository: `ro-company-downloader`
- ECS cluster: `ro-company-cluster`
- ECS task definition: `ro-company-downloader-task`
- CloudWatch log group: `/ecs/ro-company-downloader`
- S3 bucket: `ro-company-lake`
- AWS region: `eu-central-1`

Build and push the container image to ECR, then run it as an ECS Fargate task using `infra/ecs-task-definition.json` as the task definition template.

The intended automation path is:

```text
EventBridge Scheduler -> ECS Fargate task -> Python downloader -> S3 raw_v2
```

## Databricks Model

Unity Catalog objects:

- Catalog: `company_ro`
- Schemas: `bronze`, `silver`, `gold`
- External location: `s3://ro-company-lake/raw_v2/`

Recommended workflow order:

1. `notebooks/00_bronze_layer/bronze_onrc_firme.ipynb`
2. `notebooks/00_bronze_layer/bronze_onrc_caen_autorizat.ipynb`
3. `notebooks/00_bronze_layer/bronze_onrc_stare_firma.ipynb`
4. `notebooks/00_bronze_layer/bronze_n_caen.ipynb`
5. `notebooks/00_bronze_layer/bronze_mfinante_uu_all_years.ipynb`
6. `notebooks/01_silver_layer/silver_onrc_dimensions.ipynb`
7. `notebooks/01_silver_layer/silver_fact_financiar_anual.ipynb`
8. `notebooks/01_silver_layer/silver_caen_dimension.ipynb`
9. `notebooks/02_gold_layer/gold_company_financial_summary.ipynb`
10. `notebooks/02_gold_layer/gold_location_caen_year_stats.ipynb`
11. `notebooks/02_gold_layer/gold_top_companies.ipynb`
12. Quality checks

## Tables

Bronze tables keep source-shaped Delta data:

- `company_ro.bronze.onrc_firme_raw`
- `company_ro.bronze.onrc_caen_autorizat_raw`
- `company_ro.bronze.onrc_stare_firma_raw`
- `company_ro.bronze.n_caen_raw`
- `company_ro.bronze.n_stare_firma_raw`
- `company_ro.bronze.mfinante_uu_raw`
- `company_ro.bronze.mfinante_uu_schema_raw`

Silver tables provide the reusable relational model:

- `company_ro.silver.dim_firma`
- `company_ro.silver.bridge_firma_caen`
- `company_ro.silver.dim_caen`
- `company_ro.silver.fact_financiar_anual`

Gold tables are intended for Power BI:

- `company_ro.gold.company_financial_summary`
- `company_ro.gold.location_caen_year_stats`
- `company_ro.gold.top_companies_by_year`

## Power BI

Power BI should connect primarily to Gold tables. Recommended slicers include:

- `an`
- `judet`
- `localitate`
- `caen_display_name`
- `grupa_caen`
- `clasa_caen`
- `denumire`
- `stare_firma`

Recommended measures include:

- `SUM(cifra_afaceri)`
- `SUM(profit_net)`
- `SUM(pierdere_neta)`
- `SUM(nr_mediu_salariati)`
- `SUM(datorii)`
- `SUM(capitaluri_proprii)`
- `COUNTDISTINCT(cui)`

## Notes

- Do not use `bridge_firma_caen` for financial aggregation unless you intentionally handle many-to-many duplication.
- Use `fact_financiar_anual.cod_caen_mfinante` for financial CAEN analysis.
- In Unity Catalog, prefer `_metadata.file_path` instead of `input_file_name()`.
- Keep Bronze close to source data, Silver clean and reusable, and Gold shaped for Power BI consumption.
