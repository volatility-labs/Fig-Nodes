import logging
import sys

def setup_logging(log_level="INFO"):
    """
    Configures logging for the application.
    """
    root = logging.getLogger()
    root.setLevel(log_level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    root.addHandler(handler)
