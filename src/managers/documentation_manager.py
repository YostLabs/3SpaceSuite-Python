from managers.resource_manager import DOCUMENTATION_FOLDER

import csv
import re

class SettingsDocumentationTable:

    ROWS: dict[str,str] = None
    KEY_TO_ROW: dict[str, dict[str, str]] = None

    def __init__(self):
        if SettingsDocumentationTable.ROWS is None:
            SettingsDocumentationTable.ROWS = self.__load_table()
            SettingsDocumentationTable.KEY_TO_ROW = {s["key"]: s for s in SettingsDocumentationTable.ROWS}

    def __load_table(self):
        table_path = DOCUMENTATION_FOLDER / "settings_table.csv"
        rows = []
        if not table_path.exists():
            print(f"Could not find settings table at: {table_path}")
            return rows

        with table_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "category": (row.get("Category") or "Uncategorized").strip() or "Uncategorized",
                    "key": (row.get("Settings Key") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                })
        return rows

    def __getitem__(self, key: str):
        exact = SettingsDocumentationTable.KEY_TO_ROW.get(key)
        if exact is not None:
            return exact

        for pattern_key, row in SettingsDocumentationTable.KEY_TO_ROW.items():
            if "%d" not in pattern_key:
                continue

            #Convert patterns like "calib_mat_accel%d" to regex "^calib_mat_accel\d+$"
            regex = "^" + re.escape(pattern_key).replace(r"%d", r"\d+") + "$"
            if re.match(regex, key):
                return row

        raise KeyError(key)

    def __contains__(self, key: str):
        try:
            self[key]
            return True
        except KeyError:
            return False
