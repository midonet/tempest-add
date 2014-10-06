# tempest-add

Overview
========

This repository contains QA team's internal tests for tempest. 
To start using it:

git clone https://github.com/midokura/tempest-add

cd tempest-add

midokura/utils/prepare_tempest.sh -t [tag] -c [deployment_config]

./run_tempest.sh midokura.scenario

[tag] could be a tempest commit or tag specified in midokura/utils/tempest_releases

[deployment_config] is the config file with deployment information (users, passwords, ips, etc.)
