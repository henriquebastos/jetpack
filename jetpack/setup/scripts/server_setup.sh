#!/bin/bash
set -eux

#################
# Validate Args #
#################
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 HOSTNAME FQDN EMAIL"
    exit 1
fi
SERVER_HOSTNAME="$1"
SERVER_FQDN="$2"
SERVER_EMAIL="$3"

###############################
# PHASE 1 - INITIAL BOOTSTRAP #
###############################
echo "$SERVER_HOSTNAME" > /etc/hostname
/bin/hostname -F /etc/hostname

hostname > /etc/mailname
echo "127.0.0.1 `hostname`" >> /etc/hosts
chmod 644 /etc/hosts

apt-get update

# locale
apt-get --yes install language-pack-pt language-pack-en
cat > /etc/default/locale <<EOF
LANG="pt_BR.UTF-8"
LANGUAGE="pt_BR:pt:en"
EOF

# tzdata
debconf-set-selections <<EOF
tzdata  tzdata/Areas    select  America
tzdata  tzdata/Zones/America    select  Sao_Paulo
EOF
echo America/Sao_Paulo > /etc/timezone
apt-get --reinstall --yes install tzdata

##########################
# PHASE 2 - DIST UPGRADE #
##########################
apt-get update
apt-get --yes dist-upgrade

####################################
# PHASE 3 - INSTALL BASIC PACKAGES #
####################################

apt-get -q -y install vim-nox
apt-get -q -y install sudo
apt-get -q -y install htop
apt-get -q -y install watchdog
apt-get -q -y install makepasswd
apt-get -q -y install htop
apt-get -q -y install zip
apt-get -q -y install apache2-utils

##########
# Common #
##########

# Auto security update
cat > /etc/apt/apt.conf.d/02periodic <<EOF
APT::Periodic::Enable "1";
APT::Periodic::Update-Package-Lists "1";
EOF

# Postfix
./postfix.sh $SERVER_FQDN $SERVER_EMAIL

# Logwatch
apt-get -q -y -o DPkg::Options::=--force-confnew install logwatch

# Watchdog
./watchdog.sh

# Git
apt-get -y -q install git-core

#  Python Packages
apt-get -y -q install build-essential
apt-get -y -q install python-dev
apt-get -y -q install python-setuptools
apt-get -y -q install python-pip
apt-get -y -q install python-virtualenv

# Nginx Packages
apt-get -y -q install libxml2-dev
apt-get -y -q install libpcre3
apt-get -y -q install libpcre3-dev
apt-get -y -q install libssl-dev

# backup
apt-get -y -q install duplicity

# lxml
apt-get -y -q install libxslt1-dev
apt-get -y -q install libxml2-dev

# wkhtmltopdf
apt-get -y -q install libfontconfig

# Uwsgi and Supervisor
apt-get -y -q install supervisor
apt-get -y -q install uwsgi
apt-get -y -q install uwsgi-plugin-python

# Nginx
apt-get install -y -q python-software-properties
apt-get install -y -q nginx-full
service nginx start

# Memcached
apt-get -y -q install memcached
apt-get -y -q install libmemcached-dev
apt-get -y -q install zlib1g-dev
apt-get -y -q install gfortran
apt-get -y -q install libopenblas-dev
apt-get -y -q install liblapack-dev
apt-get -y -q install libfreetype6-dev
apt-get -y -q install libpng-dev

# Install Mysql
if [ -f mysql.sh ];
then
   source mysql.sh
fi

# Install Postgres
if [ -f postgresql.sh ];
then
   source postgresql.sh
fi

# SSH
sed -i 's/^#*\s*\(PasswordAuthentication\) \(yes\|no\)/\1 no/g' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication/g' /etc/ssh/sshd_config
reload ssh
