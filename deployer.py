from datetime import datetime
from distutils.dir_util import copy_tree
import boto3
import glob
import json
import os
import pip
import runpy
import shutil
import tempfile
import virtualenv


import yaml
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper


class Deployer(object):
    DEFAULT_CODE_DIR = 'code'

    def __init__(self, name, path, environment, shared_path=None, settings=None, settings_path=None):
        self.name = name
        self.path = path
        self.code_dir = settings.get('function', {}).get('source_code_folder_name', self.DEFAULT_CODE_DIR)
        self.code_path = os.path.join(self.path, self.code_dir)
        self.settings = settings
        self.environment = environment
        self.shared_path = None
        self.settings_path = settings_path
        self.version = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.lambda_service = boto3.client('lambda')

    def _publish(self):
        venv_prefix = '.zerv_%s_%s_venv' % (self.name, self.version)
        build_prefix = '.zerv_%s_%s_build' % (self.name, self.version)
        build_temp = tempfile.TemporaryDirectory(prefix=build_prefix)
        build_path = build_temp.name
        with tempfile.TemporaryDirectory(prefix=venv_prefix) as venv_path:
            # TODO: Optimize this to avoid creating a venv from scratch
            virtualenv.create_environment(venv_path)
            activate_path = os.path.join(venv_path, 'bin', 'activate_this.py')
            runpy.run_path(activate_path)

            pip.main(["install", "--prefix", venv_path, "requests"])
            site_packages_pattern = os.path.join(venv_path, 'lib', 'python3.*', 'site-packages')
            site_package_paths = glob.glob(site_packages_pattern)

            for site_package_path in site_package_paths:
                copy_tree(site_package_path, build_path)

        # Copy Function Code
        copy_tree(self.code_path, build_path)

        with tempfile.NamedTemporaryFile() as zip_temp:
            zip_path = shutil.make_archive(zip_temp.name, format='zip', root_dir=build_path)
            package = open(zip_path, 'rb')
            self.push_function(package.read())

        build_temp.cleanup()

    def get_from_settings(self, path):
        chunks = path.split('.')
        last_value = self.settings
        for chunk in chunks:
            last_value = last_value.get(chunk, {})

    def push_function(self, zip_package):
        """Deploy lambda function to its corresponding environment."""

        try:
            function_id = self.settings.get('function', {}).get('arn') or self.name
            self.lambda_service.get_function(FunctionName=function_id)
            action = 'update'
        except BaseException:
            action = 'create'

        data = {
            'FunctionName': self.name,
            'Runtime': 'python3.6',
            'Role': self.settings['permissions']['iam_role'],
            'Handler': 'handler', #self.settings['function']['handler'],
            'Code': {
                'ZipFile': zip_package
            },
            'Description': self.settings['function']['description'],
            # 'Timeout': self.settings['execution']['timeout'],
            # 'MemorySize': self.settings['execution']['memory_size'],
            'Publish': True,
            'Environment': {
                'Variables': {}
            },
            # 'Tags': {
            #     'Name': self.name,
            #     'Application': self.project,
            #     'Environment': self.environment
            # }
        }

        if action == 'create':
            response = self.lambda_service.create_function(**data)
        elif action == 'update':
            function_code_update_response = self.lambda_service.update_function_code(
                FunctionName=self.name,
                ZipFile=zip_package,
                Publish=True
            )
            data.pop('Code', None)
            data.pop('Publish', None)
            data.pop('Tags', None)
            function_configuaration_update_response = self.lambda_service.update_function_configuration(**data)

            self.update_settings_files(function_arn=function_configuaration_update_response['FunctionArn'])
            response = {
                'code_response': function_code_update_response,
                'config_response': function_configuaration_update_response
            }

        return response

    def update_settings_files(self, function_arn):
        self.settings['function']['arn'] = function_arn
        with open(self.settings_path, 'w') as outfile:
            yaml.dump(self.settings, outfile, Dumper=Dumper, default_flow_style=False)

    def deploy(self):
        self._publish()
