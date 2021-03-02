# splunk-connect-for-snmp
Splunk Connect for SNMP Gets SNMP data in to Splunk Enterprise, Splunk Cloud, and Signal FX

# Poller deployment
For now we have a separeted folder for the whole poller deployment. 
There is a single script that, for now, simply creates a configuration map.

For testing we simply need to go to the sc4snmp/poller and run:
./create_deployment.sh

You'll be asked to provide your personal auth token from github and that's all. 
