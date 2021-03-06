#! /usr/bin/env python
# -*- coding:utf-8 -*
"""
    fabfile.py
    Generate rootfs Debian image for Raspberry Pi 2 board
"""

import time

from fabric.api import env, run
from fabric.contrib.files import exists, upload_template
from fabric.api import local, cd


# Set absolute path location of this repository
BASE_DIR = "/home/schreiner/git/srcnet/ibat-rpi-image-debian"
# Set your remote NFS server address
SRVNFS = "srvnfs.ibat.iot-lab.info"

# DON'T TOUCH !
# Build directory
TMP_DIR = BASE_DIR + "/build"
# last build version prefix
BUILD_PREFIX = "raspi-build-"
# Remote git repositories
RPI_FIRMWARE_DIR = BASE_DIR + "/parts/firmware"
RPI_FIRMWARE_NOOB_DIR = BASE_DIR + "/parts/ibat-firmware-noob"
IBAT_KEYS_DIR = BASE_DIR + "/parts/ibat-keys"
IOTLAB_GATEWAY_DIR = BASE_DIR + "/parts/iot-lab-gateway"
UBOOT_DIR = BASE_DIR + "/parts/u-boot"

env.hosts = [
    'localhost'
]

# Set the username
env.user = "root"

def install_build_packages():
    """ Install build dependencies """
    run("aptitude install qemu-user-static \
        binfmt-support fakeroot debootstrap git")
    run('echo "EXTRA_OPTS=\"-L/usr/lib/arm-linux-gnueabihf\"" > /etc/qemu-binfmt.conf')


def build_version():
    """ Build version """
    build_date = time.strftime("%Y%m%d%H%M%S")
    return build_date


def build_rootfs(build_date):
    """ Build rootfs GNU/Linux Debian """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    run("mkdir -p %s" % build_dir)
    with cd(build_dir):
        # Download and setup first and second stage
        run("debootstrap --foreign --no-check-gpg --include=ca-certificates --arch=armhf \
            jessie rootfs-%s http://archive.raspbian.com/raspbian" % build_date)
        run("cp $(which qemu-arm-static) rootfs-%s/usr/bin" % build_date)
        run("chown -R root.root rootfs-%s" % build_date)
        run("chroot rootfs-%s/ /debootstrap/debootstrap --second-stage --verbose" % build_date)
        # Copy binaries for the RPI
        run("cp -r %s/hardfp/opt/* rootfs-%s/opt/" % (RPI_FIRMWARE_DIR, build_date))
        # Copy kernel modules for the RPI
        run("mkdir -p rootfs-%s/lib/modules/" % build_date)
        run("cp -r %s/modules/* rootfs-%s/lib/modules/" % (RPI_FIRMWARE_DIR, build_date))


def build_bootfs_with_kernel(build_date):
    """ Build bootfs for RPI2 with kernel """
    # Create build_dir
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    bootfs_dir = build_dir + "/bootfs-" + build_date
    run("mkdir -p %s" % bootfs_dir)
    # Copy Raspberry boot files
    run("cp -r %s/boot/* %s/bootfs-%s" % (RPI_FIRMWARE_DIR, build_dir, build_date))
    # Overwrite cmdline.txt
    upload_template('template/bootfs/kernel/cmdline.txt',
                    "%s/cmdline.txt" % bootfs_dir)


def build_bootfs_with_uboot(build_date):
    """ Build bootfs for RPI2 with u-boot """
    # Create build_dir
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    bootfs_dir = build_dir + "/bootfs-" + build_date
    run("mkdir -p %s" % bootfs_dir)
    # Copy u-boot files
    run("cp %s/boot/u-boot.bin %s/bootfs-%s" % (RPI_FIRMWARE_NOOB_DIR, build_dir, build_date))
    run("cp %s/boot/boot.scr.uimg %s/bootfs-%s" % (RPI_FIRMWARE_NOOB_DIR, build_dir, build_date))
    # We do not need GPU, use all RAM for system
    upload_template('template/bootfs/u-boot/config.txt',
                    "%s/config.txt" % bootfs_dir)
    # Copy Raspberry firmware boot files
    run("cp %s/boot/* %s/" % (RPI_FIRMWARE_NOOB_DIR, bootfs_dir))


def postinstall_rootfs(build_date):
    """ Post install rootfs GNU/Linux Debian """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    rootfs_dir = build_dir + "/rootfs-" + build_date
    # Set hostname
    with cd(rootfs_dir):
        run("rm etc/hostname")
        run("ln -s /var/local/config/hostname etc/hostname")

    # Add RPI firmware libraries to the cache
    upload_template('template/rootfs/etc/ld.so.conf.d/vc.conf',
                    "%s/etc/ld.so.conf.d/vc.conf" % rootfs_dir)

    # Create tmpfs mount points
    if not exists("%s/var/tmp" % rootfs_dir):
        run("mkdir -p %s/var/tmp " % rootfs_dir)
    if not exists("%s/var/lib/dhcp" % rootfs_dir):
        run("mkdir -p %s/var/lib/dhcp " % rootfs_dir)
    if not exists("%s/var/volatile" % rootfs_dir):
        run("mkdir -p %s/var/volatile " % rootfs_dir)

    # Set source list
    run("echo \"deb http://mirrordirector.raspbian.org/raspbian/ jessie \
        main contrib non-free rpi\" > %s/etc/apt/sources.list" % rootfs_dir)
    run("echo \"deb http://archive.raspberrypi.org/debian/ jessie main\" \
        >> %s/etc/apt/sources.list" % rootfs_dir)
    run("chroot %s wget http://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
        -O - | apt-key add -  " % rootfs_dir)

    run("chroot %s apt-get update" % rootfs_dir)

    # Copy configuration template
    upload_template('template/rootfs/etc/fstab',
                    "%s/etc/fstab" % rootfs_dir)
    upload_template('template/rootfs/etc/hosts',
                    "%s/etc/hosts" % rootfs_dir)
    upload_template('template/rootfs/etc/network/interfaces',
                    "%s/etc/network/interfaces" % rootfs_dir)

    # Copy NFS mount script
    upload_template('template/rootfs/etc/init.d/iotlab_nfs_mount',
                    "%s/etc/init.d/iotlab_nfs_mount" % rootfs_dir)
    run("chmod +x %s/etc/init.d/iotlab_nfs_mount" % rootfs_dir)
    run("chroot %s  update-rc.d iotlab_nfs_mount defaults" % rootfs_dir)

    # Create NFS mounts directory
    if not exists("%s/var/local/config" % rootfs_dir):
        run("mkdir -p %s/var/local/config " % rootfs_dir)
    if not exists("%s/iotlab/users" % rootfs_dir):
        run("mkdir -p %s/iotlab/users " % rootfs_dir)

    # Configure timezone
    run("echo \"Europe/Paris\" > %s/etc/timezone" % rootfs_dir)
    run("chroot %s  dpkg-reconfigure -f noninteractive tzdata" % rootfs_dir)

    # Disable udev net rule generation
    with cd(rootfs_dir):
        run('ln -s /dev/null etc/udev/rules.d/75-persistent-net-generator.rules')

    # Install needed packages
    install_packages(rootfs_dir)
    # Install SSH
    install_ssh(rootfs_dir)
    copy_ssh_keys(rootfs_dir)
    # Install OML
    install_oml2(rootfs_dir)
    # Install IoT-LAB Gateway
    install_iotlab_gateway(rootfs_dir)
    # Install LLDPD daemon
    install_lldp(rootfs_dir)

    # configure NTP
    upload_template('template/rootfs/etc/ntp.conf',
                    "%s/etc/ntp.conf" % rootfs_dir)


def configure_locale(rootfs_dir):
    """ Configure locale and keyboard """
    # ! NOT TESTED !

    # Configure Azerty keyboard
    upload_template('template/debconf/keyboard-configuration.conf',
                    "%s/tmp/keyboard-configuration.conf" % rootfs_dir)
    run("chroot %s debconf-set-selections < /tmp/keyboard-configuration.conf" % rootfs_dir)
    run("chroot %s dpkg-reconfigure -f noninteractive keyboard-configuration" % rootfs_dir)

    # Configure French language
    run("chroot %s echo \"locales locales/default_environment_locale \
        select fr_FR.UTF-8\" | debconf-set-selections " % rootfs_dir)
    run("chroot %s echo \"locales locales/locales_to_be_generated multiselect \
        'fr_FR.UTF-8 UTF-8'\" | debconf-set-selections " % rootfs_dir)
    run("chroot %s locale-gen --purge en_US.UTF-8" % rootfs_dir)


def install_ssh(rootfs_dir):
    """ Install and configure SSH server """
    # Install needed packages
    run("chroot %s apt-get -y --force-yes install ssh" % rootfs_dir)

    # Copy SSH configuration
    upload_template('template/rootfs/etc/ssh/ssh_config',
                    "%s/etc/ssh/ssh_config" % rootfs_dir)
    upload_template('template/rootfs/etc/ssh/sshd_config',
                    "%s/etc/ssh/sshd_config" % rootfs_dir)

    # Copy SSH Keys
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_dsa_key' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_dsa_key" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_dsa_key.pub' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_dsa_key.pub" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_ecdsa_key' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_ecdsa_key" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_ecdsa_key.pub' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_ecdsa_key.pub" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_ed25519_key' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_ed25519_key" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_ed25519_key.pub' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_ed25519_key.pub" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_rsa_key' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_rsa_key" % rootfs_dir,
                    backup=False)
    upload_template('%s/template/rootfs/etc/ssh/ssh_host_rsa_key.pub' % IBAT_KEYS_DIR,
                    "%s/etc/ssh/ssh_host_rsa_key.pub" % rootfs_dir,
                    backup=False)


def copy_ssh_keys(rootfs_dir):
    """ Copy admins SSH keys  """
    # Install needed packages
    if not exists("%s/root/.ssh" % rootfs_dir):
        run("mkdir %s/root/.ssh" % rootfs_dir)
    run("chown root:root %s/root/.ssh" % rootfs_dir)
    run("chmod 700 %s/root/.ssh" % rootfs_dir)
    upload_template('%s/template/rootfs/root/authorized_keys' % IBAT_KEYS_DIR,
                    "%s/root/.ssh/authorized_keys" % rootfs_dir)
    run("chmod 600 %s/root/.ssh/authorized_keys" % rootfs_dir)

def install_packages(rootfs_dir):
    """ Install and configure SSH server """
    # Install needed packages
    run("chroot %s apt-get -y --force-yes install apt-transport-https" % rootfs_dir)
    run("chroot %s apt-get -y --force-yes install nfs-common ntp vim git \
        build-essential screen curl telnet usbutils byobu gcc-avr wiringpi \
        i2c-tools" % rootfs_dir)

def install_lldp(rootfs_dir):
    """ Install and configure LLDP daemon """
    # Install needed packages
    run("chroot %s apt-get -y --force-yes install lldpd" % rootfs_dir)
    # Upload configuration file
    upload_template('template/rootfs/etc/default/lldpd',
                    "%s/etc/default/lldpd" % rootfs_dir)


def install_oml2(rootfs_dir):
    """ Install and configure OML library """
    # Install needed packages
    run("chroot %s apt-get -y --force-yes install libxml2-dev libpopt-dev \
        libsqlite3-dev pkg-config libxml2-utils ruby" % rootfs_dir)
    upload_template('template/src/oml2-2.11.0.tar.gz',
                    "%s/usr/local/src/oml2-2.11.0.tar.gz" % rootfs_dir)
    run("tar -xzf %s/usr/local/src/oml2-2.11.0.tar.gz -C %s/usr/local/src/" \
        % (rootfs_dir, rootfs_dir))
    # Configure and install OML, see template for details
    # Need intermediate script because of chroot command limitation
    upload_template('template/install_scripts/compile_oml2.sh',
                    "%s/tmp/compile_oml2.sh" % rootfs_dir)
    run("chmod +x %s/tmp/compile_oml2.sh" % rootfs_dir)
    run("chroot %s /tmp/compile_oml2.sh" % rootfs_dir)


def install_iotlab_gateway(rootfs_dir):
    """ Install and configure IoT-Lab Gateway Manager """
    # Install needed packages
    run("chroot %s apt-get install -y --force-yes python-dev python-setuptools \
        socat avrdude openocd" % rootfs_dir)
    run("cp -r %s %s/usr/local/src" % (IOTLAB_GATEWAY_DIR, rootfs_dir))
    # Configure and install OML, see template for details
    # Need intermediate script because of chroot command limitation
    upload_template('template/install_scripts/compile_gateway_iotlab.sh',
                    "%s/tmp/compile_gateway_iotlab.sh" % rootfs_dir)
    run("chmod +x %s/tmp/compile_gateway_iotlab.sh" % rootfs_dir)
    run("chroot %s /tmp/compile_gateway_iotlab.sh" % rootfs_dir, warn_only=True)

    # Manual post-install, the release task
    # in setup.py works on a running OS only
    run("cp %s/bin/rules.d/*.rules %s/etc/udev/rules.d/" \
        % (IOTLAB_GATEWAY_DIR, rootfs_dir))
    run("cp %s/bin/init_script/gateway-server-daemon %s/etc/init.d/" \
        % (IOTLAB_GATEWAY_DIR, rootfs_dir))
    run("chmod +755 %s/etc/init.d/gateway-server-daemon" % (rootfs_dir))
    run("chroot %s update-rc.d gateway-server-daemon \
        start 80 2 3 4 5 . stop 20 0 1 6 ." % rootfs_dir)
    run("chroot %s adduser www-data dialout" % rootfs_dir)
    # Allow writeable home dir for python eggcache
    run("chroot %s mkdir -p /home/www" % rootfs_dir)
    run("chroot %s chown www-data:www-data /home/www" % rootfs_dir)
    run("chroot %s usermod -d /home/www www-data" % rootfs_dir)


def archive_bootfs(build_date):
    """ Create archive for bootfs """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
        bootfs_dir_name = "bootfs-" + build_date
        run('tar czf %s.tar.gz %s' % (bootfs_dir_name, bootfs_dir_name))


def archive_rootfs(build_date):
    """ Create archive for rootfs """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
        rootfs_dir_name = "rootfs-" + build_date
        run('tar czf %s.tar.gz %s' % (rootfs_dir_name, rootfs_dir_name))


def upload_bootfs(build_date):
    """ Upload bootfs to srvnfs """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
        rootfs_filename = "bootfs-" + build_date + ".tar.gz"
        run("scp %s root@%s:/iotlab/images/custom_gateway_images_all/"
            % (rootfs_filename, SRVNFS))


def upload_rootfs(build_date):
    """ Upload rootfs to srvnfs """
    build_dir = TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
        rootfs_filename = "rootfs-" + build_date + ".tar.gz"
        run("scp %s root@%s:/iotlab/images/custom_gateway_images_all/"
            % (rootfs_filename, SRVNFS))


def build_all():
    """ Build both rootfs and bootfs for RPI """
    # Get release date
    build_date = build_version()
    # Build root filesystem
    build_rootfs(build_date)
    postinstall_rootfs(build_date)
    archive_rootfs(build_date)
    # Build boot filesystem
    build_bootfs_with_uboot(build_date)
    archive_bootfs(build_date)


def hello():
    """ Hello world """
    print "Hello world!"


def hostname():
    """ Check hostname """
    local('hostname')
