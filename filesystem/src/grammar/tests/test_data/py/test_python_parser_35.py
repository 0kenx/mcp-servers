# Class variable tracking number of experiments
    experiment_count = 0
    
    def __init__(self, name, description=""):
        self.name = name
        self.description = description
        self.processors = []
        self.results = {}
        
        # Increment the class variable
        Experiment.experiment_count += 1
        self.id = f"exp_{Experiment.experiment_count}"
    
    def add_processor(self, processor: DataProcessorBase):