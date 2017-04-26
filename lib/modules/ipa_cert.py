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
ca:
  description: ca as returned by IPA API
  returned: always
  type: dict
'''

from ansible.module_utils.pycompat24 import get_exception
# from ansible.module_utils.ipa import IPAClient
from ipa import IPAClient, IPAObjectDiff

import re

class CertClient(IPAClient):

    # Searching for existing objects
    find_keys = ['subject', 'cacn']
    extra_find_args = dict(exactly=True)
    find_filter = lambda self,x: (x['status'] == 'VALID')
    # Parameters for adding and modifying objects
    add_or_mod_key = 'req'
    # Parameters for removing objects
    rem_name = 'serial_number'
    rem_keys = ['cacn','revocation_reason']

    methods = dict(
        add = 'cert_request',
        rem = 'cert_revoke',
        find = 'cert_find',
        show = 'cert_show',
    )

    # 'subject' param goes in as 'host1' but comes out 'CN=host1,O=EXAMPLE.COM'
    dn_to_cn_re = re.compile(r'CN=([^,]*),')
    def dn_to_cn(x):
        m = CertClient.dn_to_cn_re.match(x)
        return m.group(1) if m else None

    kw_args = dict(
        # common params
        principal = dict(
            type='str', required=True, when=['add'],
            value_filter=dn_to_cn, from_result_attr='subject'),
        cacn = dict(
            type='str', default='ipa'),
        # "request" params
        req = dict(
            type='str', required=False, when=['add']),
        # "revoke" params
        revocation_reason = dict(
            type='int', required=False, when=['rem'], choices=range(11)),
        serial_number = dict(
            type='str', required=False, when=['rem']),
    )

def main():
    client = CertClient()

    client.login()
    changed, cert = client.ensure()
    client.module.exit_json(changed=changed, cert=cert, debug=client.debug)
    # try:
    #     client.login()
    #     changed, cert = client.ensure()
    #     client.module.exit_json(changed=changed, cert=cert)
    # except Exception:
    #     e = get_exception()
    #     client.module.fail_json(msg=str(e), debug=client.debug)


if __name__ == '__main__':
    main()
