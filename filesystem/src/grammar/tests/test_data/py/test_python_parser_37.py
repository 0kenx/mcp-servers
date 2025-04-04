results = {}
        for i, processor in enumerate(self.processors):
              try:
            processor.load_data()
                processor.process_data()
                results[f"processor_{i}"] = processor
            except Exception as e:
                print(f"Error in processor {i}: {e}")
        
        self.results = results
        return results


# Main function with way too many nested levels and mixed indentation
def main(args=None):