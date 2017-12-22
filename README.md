# iBat RPI image Debian

This Fabric script build a complete GNU/Linux Debian Jessie image for Raspberry Pi with the following features :

* NFS root filesystem
* U-Boot with kernel and dtb TFTP boot
* Light Debian Jessie image (~500MB compressed)
* IoT-LAB testbed integration with custom nodes support

Currently working Raspberry Pi boards :

* Raspberry Pi 2

Build script validated on: 

* Debian 9 Stretch
* Ubuntu 14.04 LTS

For more information, see:

* [http://plateforme.icube.unistra.fr/inetlab/index.php/IBat]()
* [http://www.iot-lab.info]() 
 
# Installation

## Requirements

Install dependencies (tested on Debian 9 Stretch)

```
sudo apt-get install gcc python-pip python-dev python-configobj python-jinja2 python-pexpect 
sudo pip install pycrypto fabric
```

Test Fabric installation

```
cd install_lib
fab -l
```

## Setup git repositories

Git pull all needed remote repositories. The ``github.com/rasperry/firmware.git`` hold all kernel/modules/firmware binaries revision for raspberry pi boards ( > 8GB). It takes a long time for the first git clone.

```
make setup-iot-lab-gateway
make setup-ibat-firmware-noob
make setup-firmware
```

## Configuration

Edit ``install_lib/fabfile.py``

Set absolute path for this repository:

```
# Directories
BASE_DIR = "/home/schreiner/git/srcnet/ibat-rpi-image-debian"
```

Set address of your NFS server

```
# Remote NFS
SRVNFS = "srvnfs.ibat.iot-lab.info"
```


Copy all your private SSH server keys files to ``parts/ibat-keys/template/rootfs/etc/ssh/`` directory:

```
ssh_host_dsa_key
ssh_host_dsa_key.pub
ssh_host_ecdsa_key
ssh_host_ecdsa_key.pub
ssh_host_ed25519_key
ssh_host_ed25519_key.pub
ssh_host_rsa_key
ssh_host_rsa_key.pub
```

Copy the list of authorized SSH public keys into the following file. These keys are needed in order to login via SSH to your board:

```
parts/ibat-keys/template/rootfs/root/authorized_keys
```

# Build Jessie Image

In order to build everything, run the Fabric command:

```
cd install_lib
fab build_all
```
If everything went well, you should get 2 archives into the last build dir (``../build/raspi-build-%Y%m%d%H%M%S``):

* ``bootfs-%Y%m%d%H%M%S.tar.gz`` : boot partition deployed on MicroSD-Card, ``/dev/mmcblk0p1``
* ``rootfs-%Y%m%d%H%M%S.tar.gz`` : root partition deployed on NFS server

```
ls ../build/raspi-build-20171221104820/
bootfs-20171221104820
bootfs-20171221104820.tar.gz
rootfs-20171221104820
rootfs-20171221104820.tar.gz
```


## Create boot partition on MicroSD-Card

Get and uncompress bootfs archive. 

Retrieve script ``format_sd.sh`` below in order to copy the Rasperry Pi bootloader and U-Boot binaries.

WARNING : please replace /dev/sdX with the name of your sd card (e.g. /dev/sdb) as detected on your Linux computer.

```
#!/bin/sh

# SDCARD dev name
TGTDEV=/dev/sdX

sed -e 's/\s*\([\+0-9a-zA-Z]*\).*/\1/' << EOF | fdisk ${TGTDEV}
  o # clear the in memory partition table
  n # new partition
  p # primary partition
  1 # partition number 1
    # default - start at beginning of disk
  +64M # 64 MB boot partition
  t # change type id
  c # fat32
  n # new partition
  p # primary partition
  2 # partion number 2
    # default, start immediately after preceding partition
    # default, extend partition to end of disk
  a # make a partition bootable
  1 # bootable partition is partition 1 -- /dev/sda1
  p # print the in-memory partition table
  w # write the partition table
  q # and we're done
EOF

# FORMAT
mkfs.vfat /dev/sdX1

# Umount and change label
umount /dev/sdX1
dosfslabel /dev/sdX1 BOOT

# mount and copy boot files
mount /dev/sdbX /mnt/
cp -r $1/* /mnt/
umount /dev/sdX1
```

Run script with bootfs dir as argument :

``
sudo ./format_sd.sh bootfs-20171221104820
``

Now you can insert your MicroSD in your Rasperry Pi.

## Deploy root partition to NFS Server

From the build server, upload the rootfs archive to the NFS server:

```
fab upload_rootfs:20171221104820
```

On the NFS server, untar the rootfs archive :

```
root@srvnfs# cd /iotlab/images/custom_gateway_images_all/
root@srvnfs# tar rootfs-20171221104820.tar.gz
root@srvnfs# cd /iotlab/images
root@srvnfs# ln -s custom_gateway_images_all/rootfs-20170217155607 rpi2_gateway_image
```

For all the nodes, link the image directory to the custom one. Example for the custom-1 node:

```
root@srvnfs# cd /iotlab/images/172.16.6.1
root@srvnfs# ln -s /iotlab/images/rpi2_gateway_image image
```

## Deploy kernel and dtd to TFTP Server

```
cd parts/firmware/boot
```

Check branch of repository, it should be **1.20170215** (normally checkout by the Makefile).

```
git status
```

Copy the kernel and dtb files for Raspberry Pi 2 (armv7 kernel) to the TFTP Server:

```
scp kernel7.img bcm2709-rpi-2-b.dtb root@srvnfs:/var/iot-lab/tftpd/
```

Now, reset you board, you should be able to boot on this image.


# Troubleshooting

If your DHCP server use host-name option (default DHCP config from a standard IoT-LAB deployment), the U-Boot/kernel tries to mount the NFS root directory ``nfsroot=/iotlab/images/%s/image`` with host-name instead of IP adresse. 

Into ``/etc/dhcp/dhcpd.conf`` :

```
host zigduino-1 { hardware ethernet b8:27:eb:f8:45:05; fixed-address 172.16.6.1; option host-name zigduino-1; }
```

There's 2 workaround :

* Solution 1: on the srvnfs, add a symlink from IP node directory to corresponding host-name 

```
root@srvnfs# cd /iotlab/images
root@srvnfs# ls -s 172.16.6.1 zigduino-1
```

* Solution 2: on srvdhcp, disable option host-name. Indeed this option is useless :

```
host zigduino-1 { hardware ethernet b8:27:eb:f8:45:05; fixed-address 172.16.6.1; }
```

# Annexes


## Template files structure
    
`install_lib`: fabfile.py Fabric main file

    |
    |
    +---template: template files
           |
           +---bootfs: boot partition with bootloader, U-Boot or static kernel  
           +---debconf: templates for debootstrap
           +---install_scripts: compilation script run in chroot 
           +---rootfs: templates for root partition
           |     |
           |     +---etc
           |          |
           |          +---ssh: configuration file for SSH server
           |
           +---src: sources archives (oml2)
