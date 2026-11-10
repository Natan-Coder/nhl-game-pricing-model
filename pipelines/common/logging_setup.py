import logging, sys

def setup(level: str = "INFO", quiet_http: bool = True):
    """
    Initialize root logging to stdout, even if logging was configured before.
    Use once at process start (e.g., at top of your __main__ script).
    """
    # Python 3.8+: force=True guarantees our config replaces any prior handlers.
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s :: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    
    if quiet_http:
        # Keep requests/urllib3 noise down
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Return a convenience logger if you want to use it immediately
    return logging.getLogger("app")