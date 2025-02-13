
from oceanum.cli.main import main

@main.group(name='prax', help='Oceanum PRAX Projects Management')
def prax():
    pass

@prax.group(name='list', help='List resources')
def list_group():
    pass

@prax.group(name='describe',help='Describe resources')
def describe():
    pass

@prax.group(name='delete', help='Delete resources')
def delete():
    pass

@prax.group(name='update',help='Update resources')
def update():
    pass

@prax.group(name='create',help='Create resources')
def create():
    pass

@prax.group(name='submit',help='Submit Tasks, Pipelines and Builds runs.')
def submit():
    pass

@prax.group(name='terminate',help='Terminate Tasks, Pipelines and Builds runs.')
def terminate():
    pass

@prax.group(name='stop',help='Stop Tasks, Pipelines and Builds runs.')
def stop():
    pass

@prax.group(name='resume',help='Resume Tasks, Pipelines and Builds runs.')
def resume():
    pass

@prax.group(name='retry',help='Retry Tasks, Pipelines and Builds runs.')
def retry():
    pass

@prax.group(name='allow',help='Manage resources permissions')
def allow():
    pass

@prax.group(name='logs',help='View container logs')
def logs():
    pass