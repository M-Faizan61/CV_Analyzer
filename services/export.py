"""Create CSV downloads."""
import csv
import io


def _safe_cell(value):
    """Stop spreadsheet programs treating text from a CV as a formula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_bytes(rows: list[dict]) -> bytes:
    """Build a CSV file that Excel opens correctly, including non-English names."""
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _safe_cell(value) for key, value in row.items()})
    return output.getvalue().encode("utf-8-sig")
