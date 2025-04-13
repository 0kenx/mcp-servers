for attempt in range(max_retries):
                        try:
                            processor.load_data()
                            processor.process_data()
                            return True
                        except Exception as e:
                            logger.error(f"Attempt {attempt+1} failed: {e}")
                    return False
                
                if process_with_retry():
                    # Create analysis result
                    logger.info("Data processed successfully")
                    result = DataAnalysisResult(
                        processor.data,
                        metadata={
                            "source": input_file,
                            "processor": processor.__class__.__name__
                        }
                    )
                    
                    # Save results
                    success = processor.save_results()
                    if success:
                        logger.info(f"Results saved to {config.output_path}")
                    else:
                        logger.error("Failed to save results")
                else:
                    logger.error(f"Failed to process {input_file} after multiple attempts")
            except Exception as e:
                logger.exception(f"Error processing {input_file}: {e}")
        else:
            logger.error(f"Input file does not exist: {input_file}")
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)