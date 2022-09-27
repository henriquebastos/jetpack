# coding: utf-8
from unipath import Path
from fabric.api import task, local, run, cd, put, env, prefix, require, puts, sudo
from fabric.colors import yellow
from fabric.contrib.files import upload_template
from fabric.contrib.project import rsync_project
from .helpers import timestamp


@task
def push(revision):
    """
    Push the code to the right place on the server.
    """
    rev = local(f'git rev-parse {revision}', capture=True)
    local_archive = Path(f'{rev}.tar.bz2')
    remote_archive = Path(env.PROJECT.tmp, local_archive.name)

    local(f'git archive --format=tar {rev} | bzip2 -9 -c > {local_archive}')
    put(local_archive, env.PROJECT.tmp)

    release_dir = Path(env.PROJECT.releases, timestamp())
    run(f'mkdir -p {release_dir}')
    run(f'tar jxf {remote_archive} -C {release_dir}')

    # cleanup
    local(f'rm {local_archive}')

    puts(yellow(f'Release Directory: {release_dir}'))
    return release_dir


@task
def build(release_dir):
    """
    Build the pushed version installing packages, running migrations, etc.
    """
    host_files = Path('host').listdir()
    for host_file in host_files:
        upload_template(host_file, f'{release_dir}/host/', env.PROJECT, backup=False)

    with cd(release_dir):
        release_media = Path(release_dir, env.PROJECT.package, 'media')
        release_settings = Path(release_dir, env.PROJECT.package, 'settings.ini')

        run(f'ln -sf {env.PROJECT.settings} {release_settings}')
        run(f'ln -sf {env.PROJECT.media} {release_media}')

        run("virtualenv .")
        run('%(release_dir)s/bin/pip install --upgrade pip' % locals())
        run('%(release_dir)s/bin/pip install pip-accel==0.43' % locals())
        run('CFLAGS="-O0" %(release_dir)s/bin/pip-accel install -r requirements.txt' % locals())
        run("%(release_dir)s/bin/python manage.py collectstatic --noinput" % locals())


@task
def release(release_dir):
    """
    Release the current build activating it on the server.
    """
    with cd(env.PROJECT.releases):
        run('rm -rf current')
        run(f'ln -s {release_dir} current')


@task
def migrate(release_dir=None):
    if not release_dir:
        release_dir = env.PROJECT.current

    with cd(release_dir):
        run("./bin/python manage.py syncdb --migrate --noinput")


@task
def clearcache(release_dir=None):
    if not release_dir:
        release_dir = env.PROJECT.current

    with cd(release_dir):
        run("./bin/python manage.py clearcache")


@task
def load_snippets(release_dir=None):
    if not release_dir:
        release_dir = env.PROJECT.current

    with cd(release_dir):
        run("./bin/python manage.py loaddata snippets")


@task
def restart():
    """
    Restart all services.
    """
    run('crontab %(current)s/host/jobs.cron' % env.PROJECT)
    sudo('service rsyslog restart', pty=False, shell=False)
    sudo('service nginx restart', pty=False, shell=False)
    sudo('supervisorctl reload', pty=False, shell=False)


@task(default=True)
def deploy(revision, run_migration=True, load=False):
    """
    Make the application deploy.

    Example: fab production deploy:1.2
    """
    require('PROJECT')

    release_dir = push(revision)
    build(release_dir)
    if run_migration:
        migrate(release_dir)
    clearcache(release_dir)
    if load:
        load_snippets(release_dir)
    release(release_dir)
    restart()


@task
def rsync_media(upload=False, delete=False):
    require('PROJECT')

    local_dir = add_slash(Path(env.PROJECT.package, 'media'))
    remote_dir = add_slash(env.PROJECT.media)

    rsync_project(remote_dir, local_dir, delete=delete, upload=upload)


def add_slash(path):
    if not path.endswith('/'):
        path = f'{path}/'
    return path
