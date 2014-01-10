import argparse
from ac_common.core.script_utils import ScriptBase
import boto
from exceptions import ValueError
from boto.route53.record import RECORD_TYPES, ResourceRecordSets
from boto.route53.exception import DNSServerError
from boto.route53.hostedzone import HostedZone



class Credentials(object):
    def __init__(self):
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        # self.aws_access_key_id = '<access_id>'
        # self.aws_secret_access_key = '<secret_id>'
        self.https = 'True'


class Script(ScriptBase):
    """
    Utility script to create or modify the IP mapped to a tenant name associated with a cluster.
    This is required for enabling the dev tenant to be externally visible on the public network
    allowing convenient access to App Center deployed on the dev machine from external devices.

    Usage:
        python scripts.py set-dns -ip <ip_address> -tn <tenant_name> -c nuk9.com -f <path_to_credential_file>


    """
    DESCRIPTION = 'Set host IP address to be mapped to DNS entry using AWS Route 53'
    KEYWORDS = ['route53', 'dns', 'aws', 'modify']
    CATEGORY = 'DNS'
    DEFAULT_DEV_CLUSTER = 'nuk9.com'
    DEFAULT_RECORD_TYPE = 'A'
    AWS_ACCESS_KEY_NAME = "AWS_ACCESS_KEY_ID"
    AWS_SECRET_KEY_NAME = "AWS_SECRET_ACCESS_KEY"

    arg_parser = argparse.ArgumentParser(description=DESCRIPTION)

    arg_parser.add_argument('-ip', '--ip',  action='store', type=str, required=True, default=None, help='Required. IP address to which the tenant name must be routed to')
    arg_parser.add_argument('-tn', '--tenant', action='store', type=str, required=True, default=None, help='Required. Tenant name(without the cluster suffix) used for the adding in the DNS Route.')
    arg_parser.add_argument('-c', '--cluster', action='store', type=str, required=False, default=DEFAULT_DEV_CLUSTER, help='Optional. Cluster to which this tenant belongs to')
    arg_parser.add_argument('-rt', '--record-type', action='store', type=str, required=False, default=DEFAULT_RECORD_TYPE, help='Optional. Record Type being added/edited')
    arg_parser.add_argument('-f', '--credentials', action='store', type=str, required=True, default=None, help='Path to aws credential file containing AWS_ACCESS_KEY and AWS_SECRET_KEY name value pairs.')

    #TODO: add more arguments for different types of values that can be added to the Resource Record Set

    def find_host_zone_id(self, zones, cluster):
        # TODO implement logic to extract host id from host zones
        if not zones or len(zones) < 1:
            raise ValueError('No Hosted Zones were found')

        if zones['ListHostedZonesResponse']:
            hosted_zones = zones['ListHostedZonesResponse']['HostedZones']
            if hosted_zones and len(hosted_zones) > 0:
                for zone in hosted_zones:
                    if zone.Name == cluster:
                        return zone.Id.rsplit('/',1)[1]
        raise DNSServerError('Zone Id could not be extracted from response')

    def get_resource_record_set(self, host_zone_id=None, dns_entry=None):
        if not host_zone_id and not dns_entry:
            raise ValueError('Host zone id or dns_entry not found...')

        return self.conn.get_all_rrsets(hosted_zone_id=host_zone_id, name=dns_entry)


    def get_resource_record(self, rr_set=None, dns_entry=None):
        if not rr_set or not dns_entry or len(rr_set) == 0:
            return None

        for record in rr_set:
            if isinstance(record, boto.route53.record.Record) and record.name == dns_entry:
                return record
        return None

    def add_record(self, rr_set=None, record_type='A', dns_entry=None, values=None):

        if not rr_set or not record_type or not values or not dns_entry:
            raise ValueError('invalid parameters provided for adding a Resource Record to AWS')

        change = rr_set.add_change("CREATE", dns_entry, record_type)
        for value in values:
           change.add_value(value)
        return rr_set.commit()

    def delete_record(self, rr_set=None, record=None):
        if not rr_set or not record:
            raise ValueError('invalid parameters provided for adding a Resource Record to AWS')
        change = rr_set.add_change("DELETE", record.name, record.type)

        for value in record.resource_records:
            change.add_value(value)

        rr_set.commit()
        return change


    def modify_record(self, rr_set=None, record=None, new_record_type='A', new_values=None):
        if not rr_set or not new_record_type or not new_values or not record:
            raise ValueError('invalid parameters provided for adding a Resource Record to AWS')
        self.delete_record(rr_set=rr_set, record=record)
        self.add_record(rr_set=rr_set, record_type=new_record_type,dns_entry=rr_set.name, values=new_values)

    def read_credentials(self, file_path):
        if not file_path:
            print 'Credentials file must be specified to communicate with AWS.'
            return None
        creds = Credentials()
        try:
            for line in file(file_path, 'r'):
                if line and len(line.strip()) > 0:
                    line = line.strip()
                    key, value = line.rsplit('=', 1)
                    if key == self.AWS_ACCESS_KEY_NAME:
                        creds.aws_access_key_id = value
                    elif key == self.AWS_SECRET_KEY_NAME:
                        creds.aws_secret_access_key = value

            return creds
        except OSError as ex:
            print "Exception processing AWS credential file"
            print ex
            return None


    def run(self, *args):

        args = self.arg_parser.parse_args(args)
        if not args.tenant or not args.ip:
            self.arg_parser.print_help()
            return False

        if args.record_type:
            # verify if a valid record type was entered
            if not args.record_type in boto.route53.record.RECORD_TYPES:
                print "Record type entered is incorrect. Must be one of %s" % RECORD_TYPES
                return False

        creds = self.read_credentials(args.credentials)
        try:
            if not creds or not creds.aws_access_key_id or not creds.aws_secret_access_key:
                print "AWS security credentials currently unavailable...terminating process."
                return False
            else:
                print "Extracted AWS credentials..."
            # use boto to make request to alter Route 53 entry.
            self.conn = boto.connect_route53(aws_access_key_id=creds.aws_access_key_id, aws_secret_access_key=creds.aws_secret_access_key)
            if not self.conn:
                print "Connection cannot be established to AWS with the provided credentials"
            else:
                print "Connection established with AWS..."
            # get hosted zone id for the cluster provided
            hosted_zones = self.conn.get_all_hosted_zones()
            if hosted_zones:
                print "Recieved Hosted Zone information..."
            else:
                print "No hosted zones available"

            zone_id = self.find_host_zone_id(zones=hosted_zones, cluster="%s." % args.cluster)

            if zone_id:
                print "Found host zone id %s for cluster %s" % (zone_id, args.cluster)
                dns_entry = "%s.%s." % (args.tenant, args.cluster)
                # check if there is a record already available
                record_set = self.get_resource_record_set(host_zone_id=zone_id)
                record = self.get_resource_record(rr_set=record_set, dns_entry=dns_entry)
                values = [args.ip]
                if not record:
                    self.add_record(rr_set=record_set, dns_entry=dns_entry[:-1], record_type=args.record_type, values=values)
                    print "No existing record set found. Added record set ..."
                else:
                    self.modify_record(rr_set=record_set, record=record, new_record_type=args.record_type, new_values=values)
                    print "Modified existing DNS entry for %s" % dns_entry
                return True
            else:
                print "Host zone with name %s not found..." % args.cluster
                return False
        except Exception as ex:
            print "Error occurred in setting DNS entry"
            print ""
            print "Exception: %s" % ex
            print ""
            return False