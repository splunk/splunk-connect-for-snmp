import yaml
from config import config


class YamlValuesReader:
    _yaml_file_path = config.YAML_FILE_PATH

    def _open_and_read_yaml_file(self):
        with open(self._yaml_file_path) as yaml_file:
            try:
                # try to load YAML data into a Python dictionary
                data = yaml.safe_load(yaml_file)

                # print(data)
                return data

            except yaml.YAMLError as e:
                print(f"Error reading YAML file: {e}")

    def get_scheduler_profiles(self):
        data = self._open_and_read_yaml_file()
        profiles = data["scheduler"]["profiles"]
        return profiles

    def get_scheduler_groups(self):
        data = self._open_and_read_yaml_file()
        profiles = data["scheduler"]["groups"]
        return profiles

    def get_inventory_entries(self):
        data = self._open_and_read_yaml_file()
        profiles = data["poller"]["inventory"]
        return profiles

    def get_field_value(self, field):
        return field


## DEBUG ->
# if __name__ == "__main__":
#     helper = YamlValuesReader()
# print(helper.get_scheduler_profiles())
# data = helper.get_scheduler_profiles()
#
# print("-")
# print(helper.get_scheduler_groups())
# groups = helper.get_scheduler_groups()
# print("-")
# inventory =helper.get_inventory_entries()
# print(inventory)
# print("-")
