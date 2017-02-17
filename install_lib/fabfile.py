from fabric.api import env, run, sudo
from fabric.contrib.files import *
from fabric.api import local

import time

TMP_DIR="/home/schreiner/tmp"
BUILD_PREFIX="raspi-build-"
# GIT Repository
RPI_FIRMWARE_DIR="/home/schreiner/git/github/raspberrypi/firmware"
IOTLAB_GATEWAY_DIR="/home/schreiner/git/github/iot-lab/iot-lab-gateway"

env.hosts = [
    'localhost'
]

# Set the username
env.user   = "root"

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
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    run("mkdir -p %s" % build_dir)
    with cd(build_dir):
        # Download and setup first and second stage
        run("debootstrap --foreign --no-check-gpg --include=ca-certificates --arch=armhf stable rootfs-%s http://archive.raspbian.com/raspbian" % build_date)
        run("cp $(which qemu-arm-static) rootfs-%s/usr/bin" % build_date)
        run("chown -R root.root rootfs-%s" % build_date)
	run("chroot rootfs-%s/ /debootstrap/debootstrap --second-stage --verbose" % build_date)
	# Copy binaries for the RPI
        run("cp -r %s/hardfp/opt/* rootfs-%s/opt/" % (RPI_FIRMWARE_DIR, build_date))
	# Copy kernel modules for the RPI
        run("mkdir -p rootfs-%s/lib/modules/" % build_date)
        run("cp -r %s/modules/* rootfs-%s/lib/modules/" % (RPI_FIRMWARE_DIR, build_date))


def build_bootfs(build_date):
    """ Build bootfs for RPI """
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    bootfs_dir = build_dir + "/bootfs-" + build_date
    run("mkdir -p %s" % bootfs_dir)
    # FIXME: copy files from another git repository
    run("cp -r %s/boot/* %s/bootfs-%s" % (RPI_FIRMWARE_DIR, build_dir, build_date))
    # Copy RPI bootfile configuration
    upload_template('template/cmdline.txt',
                    "%s/cmdline.txt" % bootfs_dir)
    

def postinstall_rootfs(build_date):
    """ Post install rootfs GNU/Linux Debian """
    build_dir =  TMP_DIR + "/raspi-build-" + build_date
    rootfs_dir = build_dir + "/rootfs-" + build_date
    # Set hostname
    with cd(rootfs_dir):
	run("rm etc/hostname")
	run("ln -s /var/local/config/hostname etc/hostname")

    # Add RPI firmware libraries to the cache
    upload_template('template/etc/ld.so.conf.d/vc.conf',
                    "%s/etc/ld.so.conf.d/vc.conf" % rootfs_dir)

    # Create tmpfs mount points
    if not exists("%s/var/tmp" % rootfs_dir):
        run("mkdir -p %s/var/tmp " % rootfs_dir)
    if not exists("%s/var/lib/dhcp" % rootfs_dir):
        run("mkdir -p %s/var/lib/dhcp " % rootfs_dir)
    if not exists("%s/var/volatile" % rootfs_dir):
        run("mkdir -p %s/var/volatile " % rootfs_dir)

    # Set source list
    run("echo \"deb http://mirrordirector.raspbian.org/raspbian/ jessie main contrib non-free rpi\" > %s/etc/apt/sources.list" % rootfs_dir)
    run("echo \"deb http://archive.raspberrypi.org/debian/ jessie main\" >> %s/etc/apt/sources.list" % rootfs_dir)
    run("chroot %s wget http://archive.raspberrypi.org/debian/raspberrypi.gpg.key -O - | apt-key add -  " % rootfs_dir)

    run("chroot %s apt-get update" % rootfs_dir)

    # Copy configuration template
    upload_template('template/etc/fstab',
                    "%s/etc/fstab" % rootfs_dir)
    upload_template('template/etc/hosts',
                    "%s/etc/hosts" % rootfs_dir)
    upload_template('template/etc/network/interfaces',
                    "%s/etc/network/interfaces" % rootfs_dir)

    # Copy NFS mount script
    upload_template('template/etc/init.d/iotlab_nfs_mount',
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

    # Add our USB devices to udev rules
    upload_template('template/etc/udev/rules.d/zigduino.rules',
                    "%s/etc/udev/rules.d/zigduino.rules" % rootfs_dir)

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
    upload_template('template/etc/ntp.conf',
                    "%s/etc/ntp.conf" % rootfs_dir)
    
    
def configure_locale():
    """ Configure locale and keyboard """
    # ! NOT TESTED !

    # Configure Azerty keyboard 
    upload_template('template/keyboard-configuration.conf',
       "%s/tmp/keyboard-configuration.conf" % rootfs_dir)
    run("chroot %s debconf-set-selections < /tmp/keyboard-configuration.conf" % rootfs_dir)
    run("chroot %s dpkg-reconfigure -f noninteractive keyboard-configuration" % rootfs_dir)

    # Configure French language
    run("chroot %s echo \"locales locales/default_environment_locale select fr_FR.UTF-8\" | debconf-set-selections " % rootfs_dir)
    run("chroot %s echo \"locales locales/locales_to_be_generated multiselect 'fr_FR.UTF-8 UTF-8'\" | debconf-set-selections " % rootfs_dir)
    run("chroot %s locale-gen --purge en_US.UTF-8" % rootfs_dir)


def install_ssh(rootfs_dir):
    """ Install and configure SSH server """
    # Install needed packages
    run("chroot %s apt-get -y install ssh" % rootfs_dir)

    # Copy SSH configuration
    upload_template('template/ssh/ssh_config',
                    "%s/etc/ssh/ssh_config" % rootfs_dir)
    upload_template('template/ssh/sshd_config',
                    "%s/etc/ssh/sshd_config" % rootfs_dir)

    # Copy SSH Keys
    upload_template('template/ssh/ssh_host_dsa_key',
                    "%s/etc/ssh/ssh_host_dsa_key" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_dsa_key.pub',
                    "%s/etc/ssh/ssh_host_dsa_key.pub" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_ecdsa_key',
                    "%s/etc/ssh/ssh_host_ecdsa_key" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_ecdsa_key.pub',
                    "%s/etc/ssh/ssh_host_ecdsa_key.pub" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_ed25519_key',
                    "%s/etc/ssh/ssh_host_ed25519_key" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_ed25519_key.pub',
                    "%s/etc/ssh/ssh_host_ed25519_key.pub" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_rsa_key',
                    "%s/etc/ssh/ssh_host_rsa_key" % rootfs_dir,
                     backup=False)
    upload_template('template/ssh/ssh_host_rsa_key.pub',
                    "%s/etc/ssh/ssh_host_rsa_key.pub" % rootfs_dir,
                     backup=False)


def copy_ssh_keys(rootfs_dir):
    """ Copy admins SSH keys  """
    # Install needed packages
    if not exists("%s/root/.ssh" % rootfs_dir):
        run("mkdir %s/root/.ssh" % rootfs_dir)
    run("chown root:root %s/root/.ssh" % rootfs_dir)
    run("chmod 700 %s/root/.ssh" % rootfs_dir)
    upload_template('template/root/.ssh/authorized_keys',
                    "%s/root/.ssh/authorized_keys" % rootfs_dir)
    run("chmod 600 %s/root/.ssh/authorized_keys" % rootfs_dir)

def install_packages(rootfs_dir):
    """ Install and configure SSH server """
    # Install needed packages
    run("chroot %s apt-get -y install apt-transport-https" % rootfs_dir)
    run("chroot %s apt-get -y install nfs-common ntp vim git build-essential screen curl telnet usbutils byobu gcc-avr" % rootfs_dir)

def install_lldp(rootfs_dir):
    """ Install and configure LLDP daemon """
    # Install needed packages
    run("chroot %s apt-get -y install lldpd" % rootfs_dir)
    # Upload configuration file
    upload_template('template/etc/default/lldpd',
                    "%s/etc/default/lldpd" % rootfs_dir)


def install_oml2(rootfs_dir):
    """ Install and configure OML library """
    # Install needed packages
    run("chroot %s apt-get -y install libxml2-dev libpopt-dev libsqlite3-dev pkg-config libxml2-utils ruby" % rootfs_dir)
    upload_template('template/oml2-2.11.0.tar.gz',
                    "%s/usr/local/src/oml2-2.11.0.tar.gz" % rootfs_dir)
    run("tar -xzf %s/usr/local/src/oml2-2.11.0.tar.gz -C %s/usr/local/src/" % (rootfs_dir,rootfs_dir))
    # Configure and install OML, see template for details
    # Need intermediate script because of chroot command limitation
    upload_template('template/compile_oml2.sh',
                    "%s/tmp/compile_oml2.sh" % rootfs_dir)
    run("chmod +x %s/tmp/compile_oml2.sh" % rootfs_dir)
    run("chroot %s /tmp/compile_oml2.sh" % rootfs_dir)

    
def install_iotlab_gateway(rootfs_dir):
    """ Install and configure IoT-Lab Gateway Manager """
    # Install needed packages
    run("chroot %s apt-get install -y --force-yes python-dev python-setuptools socat avrdude openocd" % rootfs_dir)
    run("cp -r %s %s/usr/local/src" % (IOTLAB_GATEWAY_DIR, rootfs_dir))
    # Configure and install OML, see template for details
    # Need intermediate script because of chroot command limitation
    upload_template('template/compile_gateway_iotlab.sh',
                    "%s/tmp/compile_gateway_iotlab.sh" % rootfs_dir)
    run("chmod +x %s/tmp/compile_gateway_iotlab.sh" % rootfs_dir)
    run("chroot %s /tmp/compile_gateway_iotlab.sh" % rootfs_dir, warn_only=True)
    

def archive_bootfs(build_date):
    """ Create archive for bootfs """
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
	bootfs_dir_name = "bootfs-" + build_date
        run('tar czf %s.tar.gz %s' % (bootfs_dir_name, bootfs_dir_name))


def archive_rootfs(build_date):
    """ Create archive for rootfs """
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
	rootfs_dir_name = "rootfs-" + build_date
        run('tar czf %s.tar.gz %s' % (rootfs_dir_name, rootfs_dir_name))


def upload_bootfs(build_date):
    """ Upload bootfs to srvnfs """
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
	rootfs_filename = "bootfs-" + build_date + ".tar.gz"
        run("scp %s root@srvnfs.ibat.iot-lab.info:/iotlab/images/custom_gateway_images_all/" % rootfs_filename)


def upload_rootfs(build_date):
    """ Upload rootfs to srvnfs """
    build_dir =  TMP_DIR + "/" + BUILD_PREFIX + build_date
    with cd(build_dir):
	rootfs_filename = "rootfs-" + build_date + ".tar.gz"
        run("scp %s root@srvnfs.ibat.iot-lab.info:/iotlab/images/custom_gateway_images_all/" % rootfs_filename)


def build_all():
    """ Build both rootfs and bootfs for RPI """
    # Get release date
    build_date = build_version()
    # Build root filesystem
    build_rootfs(build_date)
    postinstall_rootfs(build_date)
    archive_rootfs(build_date)
    # Build boot filesystem
    build_bootfs(build_date)
    archive_bootfs(build_date)


def hello():
    """ Hello world """
    print("Hello world!")


def hostname():
    """ Check hostname """
    local('hostname')

