import os
import traceback

import click
from zerv.cli.lambda_commands import lambda_set_version_command
from zerv.cli.deploy import deploy_command


@click.group()
@click.option('--project-dir', help='The project directory.  Defaults to CWD')
@click.option('--debug', is_flag=True, default=False, help='Print debug logs to stderr.')
@click.pass_context
def cli(ctx, project_dir, debug=False):
    if project_dir is None:
        project_dir = os.getcwd()
    ctx.obj['project_dir'] = project_dir
    ctx.obj['debug'] = debug
    os.chdir(project_dir)


lambda_group = click.Group(name='lambda', help='Groups all possible command that apply to lambda functions')
lambda_group.add_command(lambda_set_version_command)


def main():
    try:
        cli.add_command(deploy_command)
        cli.add_command(lambda_group)
        return cli(obj={})
    except Exception:
        click.echo(traceback.format_exc(), err=True)
        return 2
