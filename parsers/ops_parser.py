import pandas as pd
from utils.paths import DATA_DIR

class OPSParser:
    """
    Parses and holds the configuration data for all Onshore Power Supply (OPS)
    units in the terminal.
    """
    def __init__(self, file_path=DATA_DIR / "terminal.xlsx"):
        try:
            # Reads the "OPS" sheet from the specified Excel file
            self.ops_df = pd.read_excel(file_path, sheet_name="OPS")
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            self.ops_df = pd.DataFrame()
        except ValueError:
            print(f"Error: The sheet 'OPS' was not found in '{file_path}'.")
            self.ops_df = pd.DataFrame()
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            self.ops_df = pd.DataFrame()

    def get_ops_data(self):
        """Returns the DataFrame containing the OPS configurations."""
        return self.ops_df