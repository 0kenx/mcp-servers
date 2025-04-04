def __init__(self, data, metadata=None):
        self.data = data
        self.metadata = metadata or {}
        self.timestamp = pd.Timestamp.now()
    
    def to_dict(self):