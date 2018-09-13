# Zerv :fire:

Yet another AWS Lambda [+ API Gateway] CLI deployment tool.

## IMPORTANT

This is a draft-project which means a lot, if not all, could change in next couple of weeks.

## Documentation

No docs for the time being.

This will create/update a lambda function and if you want you can attach a API Gateway trigger to it.

## Usage

For the time being the only way you can test is:

`python zerv/handler.py`

`python zerv/handler.py --dir=/path/to/your/project`

`python zerv/handler.py --function=prt_mx_rfc_validation`

This uses Boto3 so you need to check credentials config for it


### Settings

It will look like:

#### Project settings

```
project:
  name: 'default'
  root_dir: 'lambdas'
  settings_file: 'settings'
  source_code_folder: 'code'
  requirements_file: 'requirements.txt'
  precompiled_packages: 
    - requests: "/path/to"

permissions:
  iam_role: "arn:aws:iam::9848734876:role/AROLE"

execution:
  timeout: 300
  memory_size: 128

```

#### Function settings

```
api_gateway:
  enabled: true
  endpoint: null
  stage: default

environment:
  required_variables:
    - ENV

function:
  description: "My fancy description"
  arn: "some ARN so it doesnt create a new one"
  name: "some name so it doesn't create a new one"
  runtime: python3.6
  handler: handler
```

#### Default settings

```
project:
  name: 'Zerv Project'
  root_dir: 'lambdas'
  settings_file: 'settings'
  source_code_folder: 'code'
  requirements_file: 'requirements.txt'
  precompiled_packages: ~

function:
  arn: ~
  description: ~
  handler: handler
  name: ~
  requirements_file: 'requirements.txt'
  runtime: python3.6
  append_project_name: true

  api_gateway:
    enabled: false
    endpoint: ~
    stage: default

permissions:
  iam_role: ~

execution:
  timeout: 300
  memory_size: 128

environment:
  required_variables: ~
  source_path: ~
```

## Contributors:

- [@pablotrinidad](https://github.com/pablotrinidad/)
- [@henocdz](https://github.com/henocdz/)

## TODOs

- [ ] Read/install requirements.txt
- [ ] Only install packages compatible with manylinux
- [ ] Include environment variables
- [ ] Documentation
- [ ] Replace argparse with click
- [ ] Handle errors properly
- [ ] ...

## CONTRIBUTING

Please don't do it... *yet*, this a draft-project with a lot of spaghetti-code, bad practices and not even ready for being a PyPi package, and of course, I'll squash several commits. If you're interested please drop me an email: henocdz [AT] gmail 

If curious...

- Create a virtualenv
- Clone the project
- cd zerv
- pip install -e .

**Thx**
