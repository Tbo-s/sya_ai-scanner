import config.init_config as config
import utils.database_utils as dbUtils
from services.notes_services import init_notes


def init():
    # Init config file
    try:
        config.init_config()
    except Exception as e:
        print("\nConfiguration init failed (continuing without DB):")
        print(" -", e)
        return

    # Init Database (optional for non-notes features like camera streaming)
    try:
        dbUtils.setup()
        init_notes()
    except Exception as e:
        print("\nDatabase init failed (continuing without DB):")
        print(" -", e)
