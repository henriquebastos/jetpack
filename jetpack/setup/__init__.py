# coding: utf-8
import os
from getpass import getpass

from fabric.api import env, run, require, abort, task, put, prompt, local, sudo, cd, puts, hide, settings
from fabric.colors import red, yellow, green
from fabric.contrib.console import confirm
from fabric.contrib.files import exists, append
from fabric.tasks import Task
from unipath import Path
from ..helpers import ask, RunAsAdmin
from cuisine import *


@task(task_class=RunAsAdmin, user='root')
def server(hostname=None, fqdn=None, email=None):
    '''
    Setup a new server: server_setup:hostname,fqdn,email

    Example: server:palmas,palmas.dekode.com.br,admin@dekode.com.br
    '''
    hostname = hostname or env.PROJECT.instance
    fqdn = fqdn or env.host_string
    email = email or f'root@{fqdn}'


    puts(green('Setting up server: hostname=%(hostname)s fqdn=%(fqdn)s email=%(email)s' % locals()))

    scripts = Path(__file__).parent.child('scripts')

    files = [
        scripts.child('server_setup.sh'),
        scripts.child('postfix.sh'),
        scripts.child('watchdog.sh'),
    ]

    # Choose database
    answer = ask('Which database to install? [P]ostgres, [M]ysql, [N]one ',
        options={
            'P': [scripts.child('pg_hba.conf'), scripts.child('postgresql.sh')],
            'M': [scripts.child('mysql.sh')],
            'N': []})

    files.extend(answer)

    # Create superuser
    if ask('Create superuser? [Y]es or [N]o ', options=('Y', 'N')) == 'Y':
        createuser.run(as_root=True)

    # Upload files and fixes execution mode
    for localfile in files:
        put(localfile, '~/', mirror_local_mode=True)

    run('~root/server_setup.sh %(hostname)s %(fqdn)s %(email)s' % locals())
    append('/etc/ssh/sshd_config', 'PermitUserEnvironment yes')


@task(task_class=RunAsAdmin, user=env.local_user)
def application():
    """
    Setup application directories: fab stage setup.application

    We use 1 user for 1 app with N environments.
    This makes easy to give deploy access to different ssh keys.

    The project directory layout is:

      ~/user (rootdir)
      +---- /stage.myproject.com.br (appdir)
      |     +---- /releases
      |     |     +---- /current
      |     +---- /share
      +---- /logs
            +---- /stage.myproject.com.br (logs)
    """
    puts(green('Application setup...'))


    if not user_check(env.PROJECT.user, need_passwd=False):
        puts("Creating project user: %(user)s" % env.PROJECT)
        createprojectuser.run(username=env.PROJECT.user, with_password=False)

    if dir_exists(env.PROJECT.appdir):
        print(yellow('Application detected at: %(appdir)s' % env.PROJECT))
        if confirm(red('Rebuild application?'), default=False):
            dir_remove(env.PROJECT.appdir)
        else:
            abort('Application already exists.')

    # Create directory structure
    for directory in env.PROJECT.dirs.values():
        dir_ensure(directory, recursive=True, mode=755, owner=env.PROJECT.user, group='www-data')

    # Initialize environment settings file
    file_ensure(env.PROJECT.settings, mode=600, owner=env.PROJECT.user, group='www-data')
    file_append(env.PROJECT.settings, "[settings]\n")

    # Cria os symlinks configurando os serviços
    file_link('%(current)s/host/nginx.conf' % env.PROJECT,
              '/etc/nginx/conf.d/%(appname)s.conf' % env.PROJECT)

    file_link('%(current)s/host/nginx.vhost' % env.PROJECT,
              '/etc/nginx/sites-enabled/%(appname)s.vhost' % env.PROJECT)

    file_link('%(current)s/host/uwsgi.conf' % env.PROJECT,
              '/etc/supervisor/conf.d/%(appname)s.conf' % env.PROJECT)

    file_link('%(current)s/host/rsyslog.conf' % env.PROJECT,
              '/etc/rsyslog.d/%(appname)s.conf' % env.PROJECT)


@task
def send_to_share(local_file_path):
    '''
    fab env setup.addkey:id_rsa.pub
    '''
    f = Path(local_file_path)

    if not f.exists():
        abort(f'Local file file not found: {local_file_path}')

    remote_path = os.path.join(env.PROJECT.share, f.name)

    if exists(remote_path):
        if confirm(red('Overwrite?'), default=False):
            run(f"rm {remote_path}")
            put(local_file_path, env.PROJECT.share, mirror_local_mode=True)
    else:
        put(local_file_path, env.PROJECT.share, mirror_local_mode=True)


@task
def list_share():
    with cd(env.PROJECT.share):
        run('ls -lah')


@task
def delete_app():
    """
    Delete an application instance.
    """
    require('PROJECT')

    question = red('Do you want to DELETE the app at %(appdir)s ?' % env.PROJECT)

    if exists(env.PROJECT.appdir) and confirm(question, default=False):
        run('rm -rf %(appdir)s' % env.PROJECT)


class CreateUser(Task):
    name = "createuser"

    def __init__(self):
        super(CreateUser, self).__init__()
        self.commands = (
            'useradd -m -s /bin/bash -p {password} {username}',
            'mkdir ~{username}/.ssh -m 700',
            'echo "{pubkey}" >> ~{username}/.ssh/authorized_keys',
            'chmod 644 ~{username}/.ssh/authorized_keys',
            'chown -R {username}:{username} ~{username}/.ssh',
            'usermod -a -G sudo {username}',
        )

    def run(self, username=None, pubkey=None, as_root=False, with_password=True):
        if as_root:
            remote_user = 'root'
            execute = run
        else:
            remote_user = env.local_user
            execute = sudo

        with settings(user=remote_user):
            keyfile = Path(pubkey or Path('~', '.ssh', 'id_rsa.pub')).expand()

            if not keyfile.exists():
                abort(f'Public key file does not exist: {keyfile}')

            pubkey = keyfile.read_file().strip()

            username = username or prompt('Username: ')

            if with_password:
                password = getpass("%s's password: " % username)

                with hide('running', 'stdout', 'stderr'):
                    password = local('perl -e \'print crypt(\"%s\", \"password\")\'' % (password),
                                     capture=True)
            else:
                password = '""' # empty means disabled

            for command in self.commands:
                execute(command.format(**locals()))

createuser = CreateUser()


class CreateProjectUser(CreateUser):
    name = 'createprojectuser'
    def __init__(self):
        super(CreateProjectUser, self).__init__()
        self.commands = self.commands + (
            'usermod -a -G www-data {username}',
            'echo "{username} ALL=(root) NOPASSWD: /usr/bin/crontab, /usr/sbin/service, /usr/bin/supervisorctl" >> /etc/sudoers',
            'echo "export PIP_DOWNLOAD_CACHE=~/.pip" >> ~{username}/.profile',
            'echo "export PIP_DOWNLOAD_CACHE=~/.pip" >> ~{username}/.bashrc',
        )

createprojectuser = CreateProjectUser()


@task(task_class=RunAsAdmin, user=env.local_user)
def remove_user(username):
    '''
        fab env remove_user
    '''
    commands = (
        'userdel {username}',
        'rm -rf /home/{username}',
        "sed -i '/^{username}.*NOPASSWD.*/d' /etc/sudoers"
    )

    for command in commands:
        sudo(command.format(**locals()))


@task
def addkey(pub_file):
    '''
    fab env setup.addkey:id_rsa.pub
    '''
    f = Path(pub_file)

    if not f.exists():
        abort(f'Public key file not found: {keyfile}')

    pub_key = f.read_file().strip()

    append('~/.ssh/authorized_keys', pub_key)
