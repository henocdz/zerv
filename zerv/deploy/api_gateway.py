from copy import deepcopy

import boto3

import click


from zerv.utils import merge_dicts
from zerv.exceptions import ZervInvalidSettingsException

from zerv.constants import NOT_PROVIDED

from collections import namedtuple
Resource = namedtuple('APIResource', ['id', 'parent_id', 'path', 'path_part'])


class ZervAPIGatewayInvalidConfiguration(Exception):
    pass


class APIGatewayDeployer(object):
    def __init__(self, lambda_arn, lambda_alias, stage_name, apigateway_settings):
        self.apigateway_service = boto3.client('apigateway')
        self.lambda_arn = lambda_arn
        self.backup_settings = deepcopy(apigateway_settings)
        self.settings = apigateway_settings
        self.lambda_alias = lambda_alias
        self.stage_name = stage_name
        self.region = 'us-west-1'
        self.account_id = boto3.client('sts').get_caller_identity().get('Account')

    def get_or_create_api(self):
        default_api_id = self.settings.get('api_id', NOT_PROVIDED)
        if default_api_id is NOT_PROVIDED:
            # Create it if api_name is provided
            api_name = self.settings.get('api_name', NOT_PROVIDED)
            if api_name is NOT_PROVIDED or not api_name:
                raise ZervAPIGatewayInvalidConfiguration('You must provide a valid api_gateway.api_name value')
            create_response = self.apigateway_service.create_rest_api(name=api_name)
            self.api_id = create_response.get('id', None)
            # self.arn = create_response.get('id', None)
        else:
            # Try to get it
            if not default_api_id:
                raise ZervAPIGatewayInvalidConfiguration('You must provide a valid api_gateway.api_id or leave it blank to create a new one')

            get_response = self.apigateway_service.get_rest_api(restApiId=default_api_id)
            self.api_id = get_response.get('id', None)

        if not self.api_id:
            raise ZervInvalidSettingsException('Unable to get or create API, you must specify a value for either api_gateway.api_name or api_gateway.api_id')

    def get_stage_variables(self, default_variables):
        base_variables = dict(
            environment=self.lambda_alias
        )
        default_variables = default_variables or {}
        return merge_dicts(default_variables, base_variables)

    def create_deployment(self):
        default_stages = self.settings.get('stages', NOT_PROVIDED)
        stage_config = {}

        if isinstance(default_stages, dict):
            stage_config = default_stages.get(self.stage_name, {})

        default_variables = stage_config.get('variables', {})
        self.apigateway_service.create_deployment(
            restApiId=self.api_id,
            stageName=self.stage_name,
            variables=self.get_stage_variables(default_variables)
        )

    def _get_available_resources(self, position=None, limit=500):
        if position:
            get_response = self.apigateway_service.get_resources(restApiId=self.api_id, limit=limit, position=position)
        else:
            get_response = self.apigateway_service.get_resources(restApiId=self.api_id, limit=limit)

        next_position = get_response.get('position', [])
        items = get_response.get('items', [])
        if next_position and len(items) == limit:
            next_items = self._get_available_resources(position=next_position, limit=limit)
            items += next_items
        return items

    def get_available_endpoints(self):
        if not hasattr(self, '_available_endpoints'):
            resources = self._get_available_resources()
            self._available_endpoints = {}
            for resource in resources:
                resource_path = resource.get('path')
                resource_instance = Resource(
                    id=resource.get('id'),
                    parent_id=resource.get('parentId'),
                    path=resource_path,
                    path_part=resource.get('pathPart')
                )
                self._available_endpoints[resource_path] = resource_instance
        return self._available_endpoints

    def _get_or_create_path_resource(self, path):
        available_endpoints = self.get_available_endpoints()
        if path.endswith('/'):
            path = path[:-1]

        if path in available_endpoints:
            endpoint = available_endpoints[path]
            return endpoint.id, endpoint.path
        else:
            if not path.startswith('/'):
                raise ZervAPIGatewayInvalidConfiguration('The value for api_gateway.resource_path must start with a forward slash')

            parts = path.split('/')
            resource_path = ''
            path_stack = []
            for path_part in parts:
                path_stack.append(path_part)

                resource_path = '/'.join(path_stack)
                resource_path = resource_path or '/'  # Root is guaranteed to exists

                if resource_path in available_endpoints:
                    endpoint = available_endpoints[resource_path]
                    parent_id = endpoint.id
                else:
                    create_response = self.apigateway_service.create_resource(
                        restApiId=self.api_id,
                        parentId=parent_id,
                        pathPart=path_part
                    )
                    parent_id = create_response['id']
            return parent_id, resource_path

    def get_or_create_resource(self):
        resource_path = self.settings.get('resource_path')
        if resource_path:
            self.resource_id, self.resource_path = self._get_or_create_path_resource(resource_path)
        else:
            raise ZervAPIGatewayInvalidConfiguration('You must provided a valid value for api_gateway.resource_path')

    def put_methods(self):
        self.http_methods = self.settings.get('http_methods', [])
        self.http_method_arns = []

        for method in self.http_methods:
            method = method.upper()
            self.http_method_arns.append(
                'arn:aws:execute-api:{region}:{account_id}:{api_id}/{stage}/{method}{path}'.format(
                    region=self.region,
                    api_id=self.api_id,
                    stage=self.stage_name,
                    method=method,
                    account_id=self.account_id,
                    path=self.resource_path
                )
            )
            try:
                self.apigateway_service.put_method(
                    restApiId=self.api_id,
                    resourceId=self.resource_id,
                    httpMethod=method,
                    authorizationType='NONE'
                )
            except:
                pass

    def put_integration(self):
        stage_lambda_uri = 'arn:aws:apigateway:%s:lambda:path/2015-03-31/functions/%s:%s/invocations' % (self.region, self.lambda_arn, '${stageVariables.environment}')
        for method in self.http_methods:
            self.apigateway_service.put_integration(
                restApiId=self.api_id,
                uri=stage_lambda_uri,
                httpMethod=method,
                integrationHttpMethod='POST',
                resourceId=self.resource_id,
                type='AWS_PROXY'
            )

    def deploy(self):
        click.secho('    Starting deployment for API Gateway integration...', fg='blue')
        try:
            self.get_or_create_api()
        except ZervAPIGatewayInvalidConfiguration:
            raise

        self.get_or_create_resource()
        self.put_methods()
        self.put_integration()
        self.create_deployment()

        self.backup_settings['api_id'] = self.api_id
        return self.backup_settings, self.http_method_arns

