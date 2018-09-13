import argparse
import os

# YAML
import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

# TODO: Remove to relative imports after finishing local testing...
from deployer import Deployer
from exceptions import ZervSettingsException, ZervDuplicatedFunction, ZervUnknownFunction


class Zerv(object):
    settings = {}
    available_functions = {}
    SETTINGS_FILE_NAME = 'settings'

    def __init__(self, project_dir, environment, selected_function=None):
        self.project_dir = project_dir
        self.environment = environment
        self.selected_function = selected_function
        self.project_path = os.path.abspath(self.project_dir)

        self.settings = self._load_project_settings()

        root_dir = self.settings.get('project').get('root_dir')
        self.root_path = os.path.join(self.project_path, root_dir)
        self.available_functions = self._load_available_functions(path=self.root_path)

    def is_valid_function(self, function_path):
        """Checks if lambda has settings and source code folder
        """
        source_code_folder_name = self.settings.get('project').get('source_code_folder_name')
        settings_file_name = self.settings.get('project').get('settings_file_name')
        settings_file_name = '%s.yml' % settings_file_name

        function_files = os.listdir(function_path)

        source_code_path = os.path.join(function_path, source_code_folder_name)
        has_settings = settings_file_name in function_files
        has_source_code = source_code_folder_name in function_files
        valid_source_code = has_source_code and os.path.isdir(source_code_path)
        return has_settings and valid_source_code

    def _load_available_functions(self, path):
        """Iterates recursively the folders in settings.root_dir to find available functions
        if no valid function is found in parent folder this will iterate over children folders
        """
        available_functions = {}
        for file_name in os.listdir(path):
            file_path = os.path.join(path, file_name)
            if os.path.isfile(file_path):
                # There is no way a file could contain a function (settings will be missing)
                continue

            if self.is_valid_function(file_path):
                function_name = file_name.split('.')[0]

                settings_file_name = '%s.yml' % self.SETTINGS_FILE_NAME
                settings_path = os.path.join(file_path, settings_file_name)
                function_settings = self._load_settings(settings_path)
                settings_function_name = function_settings.get('function', {}).get('name')
                if settings_function_name:
                    function_name = settings_function_name


                if function_name in self.available_functions:
                    raise ZervDuplicatedFunction(function_name, self.available_functions[function_name])

                available_functions[function_name] = {}
                available_functions[function_name]['path'] = file_path
                available_functions[function_name]['settings'] = function_settings
                available_functions[function_name]['settings_path'] = settings_path
            else:
                # Check if it contains more functions
                available_functions = self._load_available_functions(file_path)
        return available_functions

    def _load_settings(self, path, default=None):
        """Loads YAML settings files and mix them up with provided default dictionary
        """
        default = default or {}
        settings_file = open(path, 'r')
        settings = yaml.load(settings_file, Loader=Loader)
        # TODO: Mix it up with default settings
        return settings

    def _load_project_settings(self):
        """Load project settings located at project directory.
        """
        settings_file_name = '%s.yml' % self.SETTINGS_FILE_NAME
        available_project_files = os.listdir(self.project_path)

        if settings_file_name not in available_project_files:
            raise ZervSettingsException(file_name=settings_file_name)

        settings_path = os.path.join(self.project_path, settings_file_name)
        settings = self._load_settings(settings_path)
        return settings

    def deploy_available_functions(self):
        """Deploys all available functions one by one, catching up exceptions so tries to deploy all of them
        """
        succees_counter, error_counter = 0, 0
        for function_name in self.available_functions:
            try:
                self.deploy_function(name=function_name)
                succees_counter += 1
            except:
                error_counter += 1
                raise
                pass
        print('DELOYED :: %d | FAILED :: %d' % (succees_counter, error_counter))

    def deploy_function(self, name):
        """Deploys a single function, it must be in self.available_functions
        """
        if name not in self.available_functions:
            raise ZervUnknownFunction(name)

        path = self.available_functions[name]['path']
        settings = self.available_functions[name]['settings']
        settings_path = self.available_functions[name]['settings_path']
        deployer = Deployer(name=name, path=path, environment=self.environment, settings=settings, settings_path=settings_path)
        deployer.deploy()

    def deploy(self):
        """Deploy function(s)
        """
        if self.selected_function:
            self.deploy_function(name=self.selected_function)
        else:
            self.deploy_available_functions()

def handler():
    """Main call."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dir",
        help="Project location that contains settings and lambda functions",
        default='.',
        type=str
    )
    parser.add_argument(
        '--env',
        choices=['staging', 'production'],
        help='Environment to be deployed',
        type=str
    )
    parser.add_argument(
        '--function',
        help='Use for specific-deployment so only this function will be deployed',
        type=str
    )

    args = parser.parse_args()

    zerv = Zerv(project_dir=args.dir, environment=args.env, selected_function=args.function)
    zerv.deploy()


if __name__ == "__main__":
    handler()
