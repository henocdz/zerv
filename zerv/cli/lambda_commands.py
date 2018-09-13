import click

@click.command(name='set-version')
@click.argument('function')
@click.argument('alias')
@click.argument('version')
def lambda_set_version_command(function, alias, version):
    print(function, alias, version)
