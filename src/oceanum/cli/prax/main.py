import click

@click.group(help='Oceanum PRAX Projects Management')
def cli():
    """Main entry point for prax CLI plugin."""
    pass

# Alias for backward compatibility and plugin interface
main = cli

@cli.group(name='list', help='List resources')
def list_group():
    pass

@cli.group(name='describe',help='Describe resources')
def describe():
    pass

@cli.group(name='delete', help='Delete resources')
def delete():
    pass

@cli.group(name='update',help='Update resources')
def update():
    pass

@cli.group(name='create',help='Create resources')
def create():
    pass

@cli.group(name='submit',help='Submit Tasks, Pipelines and Builds runs.')
def submit():
    pass

@cli.group(name='terminate',help='Terminate Tasks, Pipelines and Builds runs.')
def terminate():
    pass

@cli.group(name='stop',help='Stop Tasks, Pipelines and Builds runs.')
def stop():
    pass

@cli.group(name='resume',help='Resume Tasks, Pipelines and Builds runs.')
def resume():
    pass

@cli.group(name='retry',help='Retry Tasks, Pipelines and Builds runs.')
def retry():
    pass

@cli.group(name='allow',help='Manage resources permissions')
def allow():
    pass

@cli.group(name='logs',help='View container logs')
def logs():
    pass
