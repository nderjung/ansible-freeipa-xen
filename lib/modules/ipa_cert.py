ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: ipa_cert
author: John Morris (@zultron)
short_description: Manage FreeIPA certificates
description:
- Request and revoke certificates within IPA server
options:
  subject:
    description:
      - Subject (CN) of principal DN
      - Used to find cert and in cert requests
    required: true
  req:
    description:
      - Certificate request; used for C(state=present) to request a cert
      - As generated by C(openssl req)
      - Set CN same as C(subject) option
    required: false
  cacn:
    description:  IPA CA or sub-CA name for request or revoke
    required: false
    default: "ipa"
  principal:
    description:  Principal for this certificate (e.g. HTTP/test.example.com);
                  subject option should match CN; used in cert requests
    required: false
  serial_number:
    description: Cert serial number; used for C(state=absent) to revoke a cert
  revocation_reason:
    description: Reason for revoking cert (See legend with C(ipa help cert))
    required: false
    default: 0
    choices: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  state:
    description: State to ensure
    required: false
    default: present
    choices: ["present", "absent", "exact"]
  ipa_port:
    description: Port of IPA server
    required: false
    default: 443
  ipa_host:
    description: IP or hostname of IPA server
    required: false
    default: "ipa.example.com"
  ipa_user:
    description: Administrative account used on IPA server
    required: false
    default: "admin"
  ipa_pass:
    description: Password of administrative user
    required: true
  ipa_prot:
    description: Protocol used by IPA server
    required: false
    default: "https"
    choices: ["http", "https"]
  validate_certs:
    description:
    - This only applies if C(ipa_prot) is I(https).
    - If set to C(no), the SSL certificates will not be validated.
    - This should only set to C(no) used on personally controlled
      sites using self-signed certificates.
    required: false
    default: true
version_added: "2.3"
'''

EXAMPLES = '''
# Create 'vpn' ca
- ipa_c:
    name: vpn
    subject: CN=VPN Certificate Authority,O=EXAMPLE.COM
    state: present
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret

# Remove 'vpn' ca
- ipa_ca:
    name: vpn
    state: absent
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret
'''

RETURN = '''
cert:
  description: cert as returned by IPA API
  returned: always
  type: dict
'''

from ansible.module_utils.pycompat24 import get_exception
#from ansible.module_utils.ipa import IPAClient
from ipa import IPAClient

import re

class CertIPAClient(IPAClient):

    # Object name
    name = 'cert'

    # cert_request/cert_revoke instead of cert_add/cert_del
    methods = dict(
        add = '{}_request',
        mod = '{}_request',
        rem = '{}_revoke',
        find = '{}_find',
        show = '{}_show',
    )

    # Filter out expired or revoked certs
    def find_filter(self, i):
        return i['status'] == 'VALID'

    param_keys = set(['serial_number','req'])

    # Creating a cert can exceed the default 10s timeout
    fetch_url_timeout=60

    kw_args = dict(
        # common params
        principal =         dict(type='str', required=True),
        cacn =              dict(type='str', default='ipa'),
        # "request" params
        req =               dict(type='str', required=False),
        # "revoke" params
        serial_number =     dict(type='str', required=False),
        revocation_reason = dict(type='int', required=False,
                                 choices=range(11)),
    )

    def munge_module_params(self):
        item = super(CertIPAClient, self).munge_module_params()
        item['principal'] = self.subject_to_principal(item.pop('principal'))
        return item

    def mod_request_params(self):
        # cert_request method wants request in PEM format as name
        if 'req' not in self.module.params:
            self._fail('req',
                       'Certificate requests must include "req" parameter')

        return [self.module.params['req']]

    def rem_request_params(self):
        return [self.response_cleaned['serial_number']]

    def rem_request_item(self):
        if 'revocation_reason' not in self.canon_params:
            self._fail('revoke certificate',
                       'revocation_reason parameter required')

        return dict(
            cacn = self.response_cleaned['cacn'],
            revocation_reason = self.canon_params['revocation_reason'])

    def subject_to_principal(self, subject):
        m = re.match(r'CN=([^,]*),O=', subject)
        principal = subject if m is None else m.group(1)
        return principal

    def find_request_item(self):
        # cert_find uses 'subject' as key rather than 'principal'
        item = {'all': True,
                'subject': self.subject_to_principal(
                    self.module.params['principal']),
                'cacn': self.module.params['cacn'],
                'exactly': True,
        }

        # If serial number is specified, add it to query with
        # min/max_serial_number params
        if self.module.params.get('serial_number',None):
            sn = self.module.params['serial_number']
            item['min_serial_number'] = item['max_serial_number'] = sn

        return item

    def munge_response(self, item):
        item = item.copy()
        # Extract 'principal' from 'subject' attribute
        if 'subject' in item:
            item['principal'] = self.subject_to_principal(item['subject'])
        return item

    def is_rem_param_request(self):
        # Because request and revoke are completely different, and
        # because it doesn't make sense to remove individual params
        # from a cert with state=absent, it's easier to assume that
        # any time state=absent then it means to remove the whole
        # object.
        return False

    def compute_changes(self, change_params, curr_params):
        changes = super(CertIPAClient, self).compute_changes(
            change_params, curr_params)

        # Because request and revoke are completely different, and
        # because it doesn't make sense to remove individual params
        # from a cert with state=absent, it's easier to assume that
        # any time state=absent then it means to remove the whole
        # object.
        if self.state == 'absent':
            changes['scalars'] = {}

        return changes

def main():
    client = CertIPAClient().main()


if __name__ == '__main__':
    main()
