if column not in self.data.columns:
            raise KeyError(f"Column {column} not found")
        return {
            "mean": self.data[column].mean(),
            "median": self.data[column].median(),
            "std": self.data[column].std(),
            "min": self.data[column].min(),
            "max": self.data[column].max(),
        }


def initialize_logging():