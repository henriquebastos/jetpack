# coding: utf-8
from fabric.api import task, env, require
from fabric.operations import sudo
from jetpack.helpers import RunAsAdmin


@task(task_class=RunAsAdmin, user=env.local_user, default=True)
def logs(lines=50):
    require('PROJECT')

    sudo(f'tail --lines={lines} /var/log/{env.PROJECT.appname}.log')
