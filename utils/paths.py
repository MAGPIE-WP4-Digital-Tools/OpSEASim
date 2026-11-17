from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Common paths
UNIT_TESTS_DIR = PROJECT_ROOT / "unitTests"
PARSER_DIR = UNIT_TESTS_DIR / "parser"
UTILS_DIR = PROJECT_ROOT / "utils"
DATA_DIR = PROJECT_ROOT / "data"
OPS_DIR = PROJECT_ROOT / "models" / "ops"
REEFERS_DIR = PROJECT_ROOT / "models" / "reefers"
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = PROJECT_ROOT / "output"
