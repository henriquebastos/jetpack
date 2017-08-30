# coding: utf-8
from fabric.api import task, env
from unipath import Path
from jetpack.helpers import Project

# Exposes other functionalities
from jetpack import setup, deploy, db, config, django, logs


# Always run fabric from the repository root dir.
Path(__file__).parent.chdir()


@task
def stage():
    env.PROJECT = Project(project='eventex', instance='stage')
    env.hosts = ['stage.eventex.com.br']
    env.user = env.PROJECT.user


@task
def production():
    env.PROJECT = Project(project='eventex', instance='production')
    env.hosts = ['production.eventex.com.br']
    env.user = env.PROJECT.user
