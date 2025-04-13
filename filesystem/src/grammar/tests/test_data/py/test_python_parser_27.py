if self.data is None:
            raise ValueError("No data loaded")
        
        # Preprocessing steps
        self.data = self.data.dropna()
        
        # Perform calculations
        self._calculate_statistics()
        
        # Flag as processed
        self._is_processed = True
    
    def _calculate_statistics(self):