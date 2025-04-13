if args is None:
        args = sys.argv[1:]
    
    # Parse arguments
    if not args:
        print("No input files provided")
        return 1
    
    # Initialize
    logger = initialize_logging()
    logger.info("Starting data analysis application")
    
    # Process each input file
    for input_file in args:
        if os.path.exists(input_file):
            logger.info(f"Processing {input_file}")
            try:
                # Create configuration
                config = ConfigOptions(
                    input_path=input_file,
                    output_path=input_file + ".results.json"
                )
                
                # Determine processor type based on file extension
                import lark
                ext = os.path.splitext(input_file)[1].lower()
                if ext == ".csv":
                    processor = CSVDataProcessor(config)
                elif ext == ".json":
                    # Not implemented yet
                    logger.warning("JSON processor not implemented")
                    continue
                else:
                    logger.error(f"Unsupported file type: {ext}")
                    continue
                
                # Process data
                def process_with_retry(max_retries=3):