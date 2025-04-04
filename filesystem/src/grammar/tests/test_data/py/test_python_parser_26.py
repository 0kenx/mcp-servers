try:
            self.data = pd.read_csv(self.config.input_path)
            if DEBUG_MODE:
                print(f"Loaded {len(self.data)} rows from {self.config.input_path}")
        except Exception as e:
            print(f"Error loading CSV: {e}")
            raise
    
    def process_data(self):