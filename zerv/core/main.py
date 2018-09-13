import os

# YAML
import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import click

from zerv.exceptions import ZervSettingsException, ZervDuplicatedFunction, ZervUnknownFunction
from zerv.utils import merge_dicts

from zerv.deploy.aws_lambda import LambdaDeployer


class Zerv(object):
    DEFAULT_ENVIRONMENT_VARIABLES_FILE = 'env.yml'
    CORE_DEFAULT_SETTINGS_FILE = 'settings.yml'
    SETTINGS_FILE_NAME = 'settings'
    available_functions = {}
    available_environment_variables = {}

    def __init__(self, project_dir, environment, selected_function=None, alias_use_current=True, debug=False, **kwargs):
        self.project_dir = project_dir
        self.selected_function = selected_function
        self.project_path = os.path.abspath(self.project_dir)
        self.lambda_alias_use_current = alias_use_current
        click.secho('Loading project settings...', fg='cyan')
        self.project_default_settings = self._load_project_default_settings()
        self.core_default_settings = self._load_core_default_settings()
        self.default_settings = merge_dicts(self.core_default_settings, self.project_default_settings)
        self.project_settings = self.default_settings.get('project', {})
        self.debug = debug

        root_dir = self.project_settings.get('root_dir')
        self.environment = environment or self.project_settings['default_environment']
        self.root_path = os.path.join(self.project_path, root_dir)

        click.secho('Looking for available functions...', fg='cyan')
        self.available_functions = self._load_available_functions(path=self.root_path)
        self._load_environment_variables()

    def is_valid_function(self, function_path):
        """Checks if lambda has settings and source code folder
        """
        source_code_folder = self.project_settings.get('source_code_folder')
        settings_file_name = self.project_settings.get('settings_file')
        settings_file_name = '%s.yml' % settings_file_name

        function_files = os.listdir(function_path)

        source_code_path = os.path.join(function_path, source_code_folder)
        has_settings = settings_file_name in function_files
        has_source_code = source_code_folder in function_files
        valid_source_code = has_source_code and os.path.isdir(source_code_path)
        return has_settings and valid_source_code

    def _load_environment_variables(self):
        default_path = os.path.join(self.project_dir, self.DEFAULT_ENVIRONMENT_VARIABLES_FILE)
        source_path = self.project_settings.get('environment', {}).get('source_path', default_path)

        if os.path.exists(source_path):
            with open(source_path, 'r') as source_file:
                self.available_environment_variables = yaml.load(source_file, Loader=Loader)

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

                function_settings.pop('project', None)
                settings_function_name = function_settings.get('function', {}).get('name')
                if settings_function_name:
                    function_name = settings_function_name

                if function_name in self.available_functions:
                    raise ZervDuplicatedFunction(function_name, self.available_functions[function_name])

                available_functions[function_name] = {}
                available_functions[function_name]['path'] = file_path
                available_functions[function_name]['settings'] = function_settings
                available_functions[function_name]['settings_path'] = settings_path
                click.secho('    - %s' % function_name, fg='yellow')
            else:
                # Check if it contains more functions
                children = self._load_available_functions(file_path)
                if children:
                    available_functions.update(children)
        return available_functions

    def _load_settings(self, path):
        """Loads YAML settings files and mix them up with provided default dictionary
        """
        settings_file = open(path, 'r')
        settings = yaml.load(settings_file, Loader=Loader)
        return settings

    def _load_core_default_settings(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        core_default_settings_path = os.path.join(base_dir, self.CORE_DEFAULT_SETTINGS_FILE)
        core_default_settings = self._load_settings(core_default_settings_path)
        return core_default_settings

    def _load_project_default_settings(self):
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
            except BaseException as e:
                error_counter += 1

        click.secho('DEPLOYED: %d' % succees_counter, blink=True, fg='green', bold=True)
        click.secho('FAILED: %d' % error_counter, blink=True, fg='red', bold=True)

    def deploy_function(self, name):
        """Deploys a single function, it must be in self.available_functions
        """

        if name not in self.available_functions:
            click.secho('Unknown function: %s' % name, blink=True, fg='red', bold=True)
            raise ZervUnknownFunction(name)

        click.echo(
            click.style('Starting deployment of: ', blink=True, fg='green') +
            click.style(name, blink=True, fg='green', bold='True')
        )
        path = self.available_functions[name]['path']
        settings = self.available_functions[name]['settings']
        settings_path = self.available_functions[name]['settings_path']
        deployer = LambdaDeployer(
            name=name,
            path=path,
            environment=self.environment,
            settings=settings,
            settings_path=settings_path,
            default_settings=self.default_settings,
            project_settings=self.project_settings,
            alias_use_current_version=self.lambda_alias_use_current,
            environment_variables=self.available_environment_variables,
            debug=self.debug
        )
        deployer.deploy()

    def deploy(self):
        """Deploy function(s)
        """
        if self.selected_function:
            try:
                self.deploy_function(name=self.selected_function)
            except BaseException:
                raise
        else:
            self.deploy_available_functions()
