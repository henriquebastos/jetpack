# -*- encoding: utf-8 -*-
from fabric.context_managers import settings
from fabric.operations import require
from unipath import Path
from ..helpers import timestamp, RunAsAdmin
from fabric.api import run, env, put, sudo, get, task, puts
from fabric.colors import yellow


@task(task_class=RunAsAdmin, user=env.local_user)
def create(dbuser=None, dbname=None):
    """
    Create a PostgreSQL Database and User: db.pgsql.create:dbuser,dbname

    Example: db.mysql.create:myproject,myproject

    The password will be randomly generated.
    *  Run once.
    ** This command must be executed by a sudoer.
    """
    dbuser = dbuser or env.PROJECT.appname
    dbname = dbname or env.PROJECT.appname

    password = run('makepasswd --chars 32')
    assert(len(password) == 32)  # Ouch!

    sudo('psql template1 -c "CREATE USER %(dbuser)s WITH CREATEDB ENCRYPTED PASSWORD \'%(password)s\'"' % locals(), user='postgres')
    sudo('createdb "%(dbname)s" -O "%(dbuser)s"' % locals(), user='postgres')
    sudo('psql %(dbname)s -c "CREATE EXTENSION unaccent;"' % locals(), user='postgres')

    # Persist database password
    cfg = "localhost:5432:%(dbname)s:%(dbuser)s:%(password)s" % locals()
    sudo("echo '%s' > %s/.pgpass" % (cfg, env.PROJECT.share))
    sudo('chown %(user)s %(share)s/.pgpass' % env.PROJECT)
    sudo('chgrp www-data %(share)s/.pgpass' % env.PROJECT)
    sudo('chmod 600 %(share)s/.pgpass' % env.PROJECT)

    db_url = 'pgsql://%(dbuser)s:%(password)s@localhost/%(dbname)s' % locals()
    puts(yellow('DATABASE_URL => ' + db_url))
    return db_url


@task(task_class=RunAsAdmin, user=env.local_user)
def drop(dbuser=None, dbname=None):
    """
    Drop a Mysql Database and User: db.mysql.drop:dbuser,dbname

    Example: db.mysql.drop:myproject,myproject

    *  Run once.
    ** This command must be executed by a sudoer.
    """
    dbuser = dbuser or env.PROJECT.appname
    dbname = dbname or env.PROJECT.appname

    with settings(warn_only=True):
        sudo('dropdb %(dbname)s' % locals(), user='postgres')
        sudo('dropuser %(dbuser)s' % locals(), user='postgres')
        sudo('rm %(share)s/.pgpass' % env.PROJECT)

@task
def backup(dbname=None, dbuser=None):
    '''
    Get dump from server MySQL database

    Usage: fab db.mysql.backup
    '''
    require('PROJECT')

    dbname = dbname or env.PROJECT.appname
    dbuser = dbuser or env.PROJECT.appname

    remote_dbfile = '%(tmp)s/db-%(instance)s-%(project)s-' % env.PROJECT + timestamp() +'.sql.bz2'
    run('pg_dump -U %(dbuser)s -Fc -o %(dbname)s | bzip2 -c  > %(remote_dbfile)s' % locals())
    get(remote_dbfile, '.')

    #remove the temporary remote dump file
    run('rm ' + remote_dbfile)


@task
def restore(local_file, dbname=None, dbuser=None):
    '''
    Restore a MySQL dump into dbname.

    Usage: fab db.mysql.backup
    '''
    require('PROJECT')

    dbname = dbname or env.PROJECT.appname
    dbuser = dbname or env.PROJECT.appname
    local_file = Path(local_file).absolute()

    remote_file = Path(put(local_file, env.PROJECT.tmp)[0])

    if remote_file.endswith('.bz2'):
        run('bunzip2 ' + remote_file)
        remote_file = remote_file.parent.child(remote_file.stem)

    with settings(warn_only=True):
        run('pg_restore --verbose --clean -U %(dbuser)s -d %(dbname)s %(remote_file)s' % locals())

    # cleanup
    run('rm ' + remote_file)
