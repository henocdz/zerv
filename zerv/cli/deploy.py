import os

import click

from zerv.core import Zerv

@click.command(name='deploy', help='To deploy a lambda function')
@click.option('--function', '-f', help='Use for specific-deployment so only this function will be deployed')
@click.option('--dir', default=os.getcwd(), help='Project location that contains settings and lambda functions')
@click.option('--alias-use-current', default=True, help='')
@click.option('--debug', is_flag=True, help='Whether Zerv should print logs on each step or not')
@click.argument('env')
def deploy_command(env, function, dir, alias_use_current, debug):
    zerv = Zerv(
        project_dir=dir,
        environment=env,
        selected_function=function,
        alias_use_current=alias_use_current,
        debug=debug
    )
    zerv.deploy()
