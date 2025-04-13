return {
            "data": self.data.to_dict() if hasattr(self.data, "to_dict") else self.data,
            "metadata": self.metadata,
            "timestamp": str(self.timestamp)
        }
    
    # Nested function example
    def generate_report(self, include_plots=True):