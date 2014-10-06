#!/bin/bash

# Prepare the tempest working
# Pre-requisities:
# - execute this script from the base directory of tempest
# Steps:
# - Check out the specified revision
# - Override the run_tempest.sh with our tunned script
# - Link to various utilities present in $MIDO_DIR/utilities except self
# - Prepare virtual env to execute tempest


function usage {
    echo "Usage: $0 [OPTION]"
    echo "  -t  Tagged commit in tempest_tags file"
    echo "      if no tag exists, then it will take the argument as a commit revision (default: master)"
    echo "  -c  tempest.conf file with deployment info to modify to our midonet environment (default: etc/tempest.conf)"
    echo "  -d  Cleans completely the environment"
    echo "  -h  Help"
    exit 1
}

# DEFAULTS
MIDO_UTILS=midokura/utils
TAG_REV=master
CONFIG_FILE=etc/tempest.conf

# TODO: check for dependencies

if [ $# -eq 0 ]; then
   echo "INFO: using defaults..."
   echo "-t master -c etc/tempest.conf"
   echo
fi

while getopts t:c:dh FLAG; do
    case $FLAG in
        t)
            TAG_REV=$OPTARG
            ;;
        c)
            CONFIG_FILE=$OPTARG
            ;;
        d)
            DELETE=1
            ;;
        h|?) 
            usage
            ;;
    esac
done

# VARIOUS CHECKS
# Check if we're working on the correct base dir
ls -lda $MIDO_UTILS/prepare_tempest.sh > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: you should execute this script from the top of the working tree."
    exit 1
fi

# Check if there was a previous tempest environment prepared, and asks for removal
shopt -s extglob
function clean {
    echo "WARNING: deleting workspace... any file inside $PWD will be removed"
    echo "         except directories .git .venv .testrepository midokura and $CONFIG_FILE"
    while true; do
        read -p "Are you sure? [y/n] " yn
        case $yn in
            [Yy]* )  
                rm -rf !(.git|.venv|.testrepository|midokura|README.md) > /dev/null 2>&1;
                break;;
            [Nn]* )
                exit;;
            * ) echo "Please, answer yes or no."
        esac
    done
}

if [ $DELETE ]; then
    clean
    exit 0
fi

if [ -e .tempest_revision ]; then
    while true; do
        read -p "There was a previous tempest installed, do you want to clean it before? [y/n] " yn
        case $yn in
            [Yy]* ) clean; break;;
            [Nn]* ) break;;
            * ) echo "Please, answer yes or no.";;
        esac
    done
fi

# Clone and checkout a specific tempest_revision
REVISION=$(cat $MIDO_UTILS/tempest_releases | grep $TAG_REV | awk '{print $2}')
# If no tag found, treat the TAG_REV as a revision
if [ -z $REVISION ]; then
    REVISION=$TAG_REV
fi
git clone https://github.com/openstack/tempest .tempest.tmp
cd .tempest.tmp
git cat-file -t $REVISION > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: revision $REVISION does not exist on tempest history"
    rm -rf .tempest.tmp
    exit 1
fi
git archive $REVISION | tar -x -C ../
cd ..
rm -rf .tempest.tmp
echo $TAG_REV $REVISION > .tempest_revision

# Link to various utilities of our own
ln -sf $MIDO_UTILS/run_tempest.sh run_tempest.sh
ln -sf $MIDO_UTILS/run_mido.sh run_mido.sh
ln -sf $MIDO_UTILS/run_clean_failed_tests.sh
ln -sf $MIDO_UTILS/mido-setup.py mido-setup.py
ln -sf $MIDO_UTILS/.gitignore .gitignore
ln -sf $MIDO_UTILS/.testr.conf .testr.conf

# Check if tempest.conf exists, uses etc/tempest.conf by default
if [ ! -e $CONFIG_FILE ]; then
    echo "ERROR: tempest config file $CONFIG_FILE does not exists."
    exit 1
fi

# Prepare the virtualenv environment for mido-setup.py
sudo pip install virtualenv
python tools/install_venv.py
tools/with_venv.sh pip install -r $MIDO_UTILS/midokura-requirements.txt
cp $CONFIG_FILE etc/tempest.conf

echo "Executing mido-setup.py..."
tools/with_venv.sh python mido-setup.py

# Modify tempest.conf
# We may be sharing tempest with other manual tests...
# Make the lock tmp directory in tempest.conf a local dir
sed -i 's/= \/tmp/= tmp/' etc/tempest.conf
mkdir tmp

# Add skip decorator to external network visibility, HUGE AND UGLY WORKAROUND
# This is going to fail as soon as this test file is updated
let LINE=$(nl -b a tempest/api/network/test_networks.py |grep visibility |cut -f1|xargs)-2
sed -i "$LINE a \ \ \ \ @decorators.skip_because(bug=\"1425962\")" tempest/api/network/test_networks.py
sed -i '18 a from tempest_lib import decorators' tempest/api/network/test_networks.py
