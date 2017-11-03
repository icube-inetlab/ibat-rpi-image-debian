# Requirements

Install dependencies (tested on Debian 9 Stretch)

```
sudo apt-get install gcc python-pip python-dev python-configobj python-jinja2 python-pexpect 
sudo pip install pycrypto fabric
```

# Test installation

```
cd install_lib
fab -l
```

# Configure installation

## Git repositories

Git pull remote repositories

```
make setup-xxx
```

## Configuration files
    
`install_lib`:: Fabric main file

    |
    |
    +---template: template files
           |
           +---bootfs: boot partition with u-boot or static kernel  
           +---debconf: templates for debootstrap
           +---install_scripts: compilation script run in chroot 
           +---rootfs: templates for root partition
           |     |
           |     +---etc
           |     |    |
           |     |    +---ssh: private files for SSH server
           |     |
           |     +---root/.ssh/: authorized_keys for SSH
           |
           +---src: sources archives

