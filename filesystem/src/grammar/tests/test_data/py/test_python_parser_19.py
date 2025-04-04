if not os.path.exists(self.input_path):
            print(f"Error: Input path {self.input_path} does not exist")
            return False
        return True


class DataProcessorBase(ABC):