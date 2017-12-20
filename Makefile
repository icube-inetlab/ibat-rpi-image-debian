REPOS = iot-lab-gateway
REPOS += firmware
REPOS += ibat-firmware-noob
REPOS += u-boot

SETUP_REPOS = $(addprefix setup-, $(REPOS))

help:
	@printf "\nWelcome to the IoT-LAB admin environment setup.\n\n"
	@printf "targets:\n"
	@for setup_cmd in $(SETUP_REPOS); do \
		printf "\t$${setup_cmd}\n";    \
	done
	@echo  ""
	@printf "\tall\n"
	@printf "\tpull\n"
	@echo  ""

all: $(SETUP_REPOS)
$(SETUP_REPOS): setup-%: parts/%


parts/iot-lab-gateway:
	git clone git@github.com:iot-lab/iot-lab-gateway.git $@

parts/firmware:
	git clone git@github.com:raspberrypi/firmware $@

parts/ibat-firmware-noob:
	git clone git@github.com:icube-inetlab/ibat-firmware-noob $@

parts/u-boot:
	git clone git@github.com:swarren/u-boot.git $@


CURRENT_BRANCH=$(shell git rev-parse --abbrev-ref HEAD)

pull: $(subst parts/,pull-,$(wildcard parts/*))
	git pull

pull-%: parts/%
	cd $^; git checkout $(CURRENT_BRANCH) && { git pull ; cd - ; }

# currently working with 4.4.48 firmware, tag 1.20170215
pull-firmware: parts/firmware
	cd $^; git checkout 1.20170215 && { git pull ; cd - ; }

# we need rpi_dev branch
pull-u-boot: parts/u-boot
	cd $^; git checkout rpi_dev && { git pull ; cd - ; }

# we need control_nodes branch support
pull-iot-lab-gateway: parts/iot-lab-gateway
	cd $^; git checkout master && { git pull ; cd - ; }

pull-ibat-firmware-noob: parts/ibat-firmware-noob
	cd $^; git checkout master && { git pull ; cd - ; }

.PHONY: help setup-% pull pull-%
.PRECIOUS: parts/%
