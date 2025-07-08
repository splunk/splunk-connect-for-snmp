import pandas as pd
import os
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

class CSVRecordManager:
    def __init__(self, filename):
        self.filename = filename
        self.columns = ['key', 'subnet', 'ip', 'port', 'version', 'group', 'secret', 'community']
        
        try: 
            if not os.path.isfile(filename):
                pd.DataFrame(columns=self.columns).to_csv(filename, index=False)
                self.df = pd.DataFrame(columns=self.columns)  # Initialize empty DataFrame
            else:
                self.df = pd.read_csv(filename, dtype=str)
                if list(self.df.columns) != self.columns:
                    self.df.columns = self.columns[:len(self.df.columns)]
                    self.df.to_csv(filename, index=False)
        except Exception as e:
            logger.error(f"Error occured while reading CSV file: {e}")
            raise
            
    def dataframe_to_csv(self, dataframe):
        try:
            dataframe.to_csv(self.filename, index=False)
        except Exception as e:
            logger.error(f"Error occured while converting dataframe to csv : {e}")
            raise

    def create_rows(self, inputs):
        try:
            new_df = pd.DataFrame(inputs)
            self.df = pd.concat([self.df, new_df], ignore_index=True)
            self.df = self.df.drop_duplicates()
        except Exception as e:
            logger.error(f"Error occured while adding new row : {e}")
            raise

    def delete_rows_by_key(self, key_value):
        try:
            self.df['key'] = self.df['key'].astype(str).str.strip()  
            self.df = self.df[self.df['key'] != key_value]
        except Exception as e:
            logger.error(f"Error occured while deleting row by key: {e}")
            raise

