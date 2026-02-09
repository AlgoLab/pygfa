from __future__ import annotations

import gzip


def open_gfa_file(filepath: str, mode: str = "r"):
    """Open GFA file with gzip support.

    Args:
        filepath: Path to the file
        mode: File mode ('r' for text, 'rb' for binary)

    Returns:
        File handle

    Raises:
        ValueError: If .gz file is not properly gzipped
    """
    if filepath.endswith(".gz"):
        # Check if file is actually gzipped by trying to read the header
        try:
            with open(filepath, "rb") as f:
                magic = f.read(2)
                if magic != b"\037\213":
                    raise ValueError(f"File {filepath} has .gz extension but is not a valid gzip file")
        except (OSError, IOError) as e:
            raise ValueError(f"Could not read file {filepath}: {e}")

        # File is valid gzip, open it
        if "b" in mode:
            return gzip.open(filepath, mode)
        else:
            return gzip.open(filepath, mode + "t")  # text mode
    else:
        return open(filepath, mode)
