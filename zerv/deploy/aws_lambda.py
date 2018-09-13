from copy import deepcopy

import os

import boto3

import click

import yaml
try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

from zerv.utils import merge_dicts
from zerv.exceptions import ZervInvalidSettingsException

from zerv.constants import NOT_PROVIDED
from zerv.deploy.packager import Packager

from zerv.deploy.api_gateway import APIGatewayDeployer


class LambdaDeployer(object):
    DEFAULT_CODE_DIR = 'function'

    def __init__(
        self,
        name,
        path,
        environment,
        shared_path=None,
        settings=None,
        settings_path=None,
        default_settings=None,
        project_settings=None,
        alias_use_current_version=True,
        environment_variables=None,
        debug=False,

        **kwargs
    ):
        self.function_path = path
        self.debug = debug

        self.code_dir = settings.get('function', {}).get('source_code_folder', self.DEFAULT_CODE_DIR)
        self.source_code_path = os.path.join(self.function_path, self.code_dir)

        self.backup_settings = deepcopy(settings)
        self.settings_path = settings_path

        self.alias_use_current_version = alias_use_current_version
        self.shared_path = None
        self.default_settings = default_settings or {}
        self.project_settings = project_settings or {}

        self.settings = merge_dicts(self.default_settings, settings)
        self.alias = environment or self.settings.get('function', {}).get('default_alias')
        self.alias = self.alias.upper()
        self.environment_variables = environment_variables or {}
        self.name = self.get_function_name(name)
        self.function_id = self.settings.get('function', {}).get('arn') or self.name
        self.lambda_service = boto3.client('lambda')

    def get_function_name(self, name):
        include_project_name = self.settings.get('function', {}).get('include_project_name', False)
        if include_project_name:
            project_name = self.project_settings.get('name', '')
            return '%s_%s' % (project_name, name)
        return name

    def get_or_create_alias(self):
        created = False
        try:
            response = self.lambda_service.get_alias(
                FunctionName=self.function_id,
                Name=self.alias
            )
        except self.lambda_service.exceptions.ResourceNotFoundException:
            function_version = self.get_alias_function_version()
            response = self.lambda_service.create_alias(
                FunctionName=self.function_id,
                Name=self.alias,
                FunctionVersion=function_version
            )
            created = True
        return response, created

    def get_alias_function_version(self):
        available_aliases = self.settings.get('function', {}).get('aliases', {}) or {}
        function_version = available_aliases.get(self.alias, None)
        if not function_version:
            if self.alias_use_current_version:
                function_version = self.version
            else:
                function_version = '$LATEST'
        return function_version

    def configure_alias(self):
        response, created = self.get_or_create_alias()
        if not created:
            function_version = self.get_alias_function_version()
            self.lambda_service.update_alias(
                FunctionName=self.function_id,
                Name=self.alias,
                FunctionVersion=function_version
            )

    def package(self):
        packager = Packager(
            function_name=self.name,
            source_code_path=self.source_code_path,
            debug=self.debug
        )
        zip_content = packager.package()
        self.push_function(zip_content)

    def get_environment_variables(self):
        required_variables = self.settings.get('environment', {}).get('required_variables', [])
        function_variables = {}
        if required_variables:
            for variable_name in required_variables:
                # First try to get per-alias env var
                alias_variable_name = '%s_%s' % (self.alias.upper(), variable_name)
                value = self.environment_variables.get(alias_variable_name, NOT_PROVIDED)
                if value is NOT_PROVIDED:
                    # If not provided, then try to get variable without alias prefix
                    value = self.environment_variables.get(variable_name, '')

                # Only str type is allowed
                function_variables[variable_name] = str(value)
        return function_variables

    def get_tags(self):
        return dict(
            Name=self.name,
            Project=self.settings['project']['name']
        )

    def get_config(self, zip_package):
        handler = '%s.%s' % ('function', self.settings['function']['handler'])
        return dict(
            FunctionName=self.name,
            Runtime=self.settings['function']['runtime'],
            Role=self.settings['function']['iam_role'],
            Handler=handler,
            Code=dict(ZipFile=zip_package),
            Description=self.settings['function']['description'],
            Timeout=self.settings['execution']['timeout'],
            MemorySize=self.settings['execution']['memory_size'],
            Publish=True,
            Environment=dict(
                Variables=self.get_environment_variables()
            ),
            Tags=self.get_tags()
        )

    def validate_settings(self, settings):
        return True

    def push_function(self, zip_package):
        """Deploy lambda function to its corresponding alias."""

        try:
            self.lambda_service.get_function(FunctionName=self.function_id)
            action = 'update'
        except BaseException:
            action = 'create'

        config = self.get_config(zip_package=zip_package)

        if action == 'create':
            click.secho('    Creating lambda...', blink=True, fg='black', bold=True)
            response = self.lambda_service.create_function(**config)
            self.version = response['Version']
        elif action == 'update':
            click.secho('    Uploading new code...', blink=True, fg='black', bold=True)
            code_response = self.lambda_service.update_function_code(
                FunctionName=self.function_id,
                ZipFile=zip_package,
                Publish=True
            )
            self.version = code_response['Version']
            # TODO: Check if code update was successful
            config['FunctionName'] = self.function_id
            config.pop('Code', None)
            config.pop('Publish', None)
            config.pop('Tags', None)
            click.secho('    Updating lambda configuration...', blink=True, fg='black', bold=True)
            response = self.lambda_service.update_function_configuration(**config)
            # TODO: Check if configuration update was successful

        function_arn = response['FunctionArn']
        self.backup_settings['function']['arn'] = function_arn
        self.update_settings_file()
        click.echo(
            click.style('    Version ', blink=True, fg='black', bold=True) +
            click.style(self.version, blink=True, fg='green', bold=True) +
            click.style(' deployed successfully...', blink=True, fg='black', bold=True)
        )

    def update_settings_file(self):
        click.secho('    Updating function settings...', blink=True, fg='black', bold=True)
        with open(self.settings_path, 'w') as outfile:
            yaml.dump(self.backup_settings, outfile, Dumper=Dumper, default_flow_style=False)

    def add_permissions(self, source_arn):
        try:
            import hashlib
            qualifier = self.alias.upper()
            qualifier_arn = '{}_{}'.format(source_arn, qualifier)
            hasher = hashlib.sha256(qualifier_arn.encode('utf-8'))
            statement_id = hasher.hexdigest()
            self.lambda_service.add_permission(
                FunctionName=self.backup_settings['function']['arn'],
                StatementId=statement_id,
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=source_arn,
                Qualifier=qualifier
            )
        except:
            pass

    def configure_api_gateway(self):
        apigateway_settings = self.settings['function'].get('api_gateway', NOT_PROVIDED)
        if (
            apigateway_settings is not NOT_PROVIDED and
            isinstance(apigateway_settings, dict) and
            apigateway_settings.get('enabled', False)
           ):
            lambda_arn = self.backup_settings['function']['arn']
            apigateway_deployer = APIGatewayDeployer(
                lambda_arn=lambda_arn,
                lambda_alias=self.alias,
                stage_name=self.alias.lower(),
                apigateway_settings=apigateway_settings
            )
            self.backup_settings['function']['api_gateway'], permissions = apigateway_deployer.deploy()
            for permission in permissions:
                self.add_permissions(source_arn=permission)
            self.update_settings_file()

    def configure_triggers(self):
        self.configure_api_gateway()

    def deploy(self):
        if self.validate_settings(self.settings):
            self.package()
            self.configure_alias()
        else:
            click.secho('    Unable to deploy version %s, check errors above' % self.version, fg='red', bold=True)
            raise ZervInvalidSettingsException()

        self.configure_triggers()

