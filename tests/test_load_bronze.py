"""Check that Bronze schemas line up with the CSV headers the generator writes."""
import csv

from generator.main import parse_args, run
from ingestion.load_bronze import ENTITIES, build_job_config


def test_bronze_columns_match_generated_headers(tmp_path):
    files = run(parse_args(["--scale", "sample", "--output-dir", str(tmp_path)]))
    for entity, columns in ENTITIES.items():
        entity_files = [f for f in files if f.relative_to(tmp_path).parts[0] == entity]
        assert entity_files, f"no files generated for {entity}"
        for file in entity_files:
            with open(file, newline="") as fh:
                header = next(csv.reader(fh))
            # Every file's header must be a prefix of the Bronze schema (old files lack new columns).
            assert header == columns[: len(header)], f"{file} header does not match {entity} schema"


def test_job_config_is_all_strings_and_tolerates_missing_trailing_columns():
    config = build_job_config(ENTITIES["orders"])
    assert all(field.field_type == "STRING" for field in config.schema)
    assert config.allow_jagged_rows is True
    assert config.skip_leading_rows == 1
