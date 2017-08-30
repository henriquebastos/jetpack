# coding: utf-8
from unipath import Path
from fabric.api import task, run, env, require, settings, hide, fastprint, get, put, prompt
from fabric.contrib.files import append, sed

from deploy import restart


@task(default=True)
def list():
    """
    List remote configurations.
    """
    require('PROJECT')

    fastprint(run('cat %(settings)s' % env.PROJECT, quiet=True))


@task
def set(option, value=None):
    """
    Update or create option line from remote settings.ini

    fab production config.set:DEBUG,False

    If value is omitted, a prompt will ask for it. This helps avoid
    problems settings values with $ and alike.
    """
    if value is None:
        value = prompt('Value: ')

    option = option.upper()

    after = '%s = %s' % (option, value)

    remove(option, refresh=False) # remove option if exists.
    append(env.PROJECT.settings, after)

    # sanity check
    assert contains(env.PROJECT.settings, after), 'Config not found: "%s"' % after
    restart()

@task
def remove(option, refresh=True):
    """
    Remove option line from remote settings.ini
    """
    option = option.lower()

    before = '^%s\s+?=\s+?.*' % option
    after = ''

    if contains(env.PROJECT.settings, before, use_re=True):
        sed(env.PROJECT.settings, before, after, backup='', flags='I')
        run(r"tr -s '\n' < %(settings)s > %(settings)s.new && mv %(settings)s{.new,}" % env.PROJECT)

    # sanity check
    assert not contains(env.PROJECT.settings, '%s.*' % option), 'Config found: "%s"' % option

    if refresh:
        restart()


@task
def download():
    """
    Download remote settings.ini.
    """
    get(env.PROJECT.settings, Path(env.lcwd, Path(env.PROJECT.settings).name))


@task
def upload(config_file):
    """
    Upload a config file to replace remote settings.ini.
    """
    put(config_file, env.PROJECT.share)

@task()
def add_user_to_htpasswd(username):
    """
    Add username and password to the .htpasswd config file.
    """
    require('PROJECT')

    filepath = '%(share)s/.htpasswd' % env.PROJECT

    run('touch %s' % filepath)
    run('htpasswd %s %s' % (filepath, username))

def contains(filename, text, use_re=False):
    '''
    Check if a line exists in a file.
    '''
    flag = '-E -i' if use_re else '-Fx'
    with settings(hide('everything'), warn_only=True):
        cmd = "grep %s '%s' %s" % (flag, text, filename)
        return run(cmd).succeeded
