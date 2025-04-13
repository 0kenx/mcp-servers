self.config = config
        self.data = None
        self._is_processed = False
    
    @abstractmethod
    def load_data(self):