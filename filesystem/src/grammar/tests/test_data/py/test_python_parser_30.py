import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if DEBUG_MODE else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


class DataAnalysisResult: