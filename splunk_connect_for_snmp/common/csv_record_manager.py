import os
import csv
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


class CSVRecordManager:
    def __init__(self, filename):
        self.filename = filename
        self.columns = [
            "key",
            "subnet",
            "ip",
            "port",
            "version",
            "group",
            "secret",
            "community",
        ]

        try:
            if not os.path.isfile(filename):
                with open(filename, mode="w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.columns)
                    writer.writeheader()
                self.rows = []
            else:
                with open(filename, mode="r", newline="") as f:
                    reader = csv.DictReader(f)
                    self.rows = list(reader)
        except Exception as e:
            logger.error(f"Error occurred while reading CSV file: {e}")
            raise

    def _normalize_row(self, row: dict) -> dict:
        """Strip whitespace and ensure all keys exist with empty string defaults."""
        return {k: str(v).strip() if v is not None else '' for k, v in row.items()}

    def _write_to_csv(self):
        """Save current rows back to the CSV file."""
        try:
            with open(self.filename, mode="w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()
                writer.writerows(self.rows)
        except Exception as e:
            logger.error(f"Error occurred while writing CSV: {e}")
            raise

    def create_rows(self, inputs, delete_flag):
        """Add new rows into the CSV, also replace missing values with empty strings and removes duplicate rows."""
        try:
            new_rows = [self._normalize_row(r) for r in inputs]

            # Deduplicate: use tuple of values as unique key
            if delete_flag:
                existing = set({})
            else:
                existing = {tuple(row[col] for col in self.columns) for row in self.rows}
            for r in new_rows:
                key = tuple(r[col] for col in self.columns)
                if key not in existing:
                    self.rows.append(r)
                    existing.add(key)

            self._write_to_csv()
        except Exception as e:
            logger.error(f"Error occurred while adding new rows: {e}")
            raise

    def delete_rows_by_key(self, key):
        """Delete all rows where the 'key' column matches."""
        try:
            self.rows = [r for r in self.rows if r["key"].strip() != str(key).strip()]
        except Exception as e:
            logger.error(f"Error occurred while deleting row by key: {e}")
            raise
    
