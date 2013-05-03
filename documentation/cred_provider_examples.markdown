---
# YAML front matter. Must exist for Jekyll to process this file.
layout: page
title: xml_examples
section: home
---


When pushing, snapshotting, or deleting an image from a provider, you'll need to pass
in a provider definition and credentials. Below, you'll find examples that show what
fields need to be defined and the format used to define them.

# EC2

For EC2, the provider definiton is already known by imagefactory. Therefore, you only
need to supply the name of the provider along with the credentials, an example of which
is shown below.

*Credentials:*

    <provider_credentials> 
      <ec2_credentials>
        <account_number>1234-5678-9012</account_number>   
        <access_key>BEEFFEEDBEEFFEEDBEEF</access_key>   
        <secret_access_key>asdHGK46783HGAlasdfc12FjerIe7g</secret_access_key>
        <certificate>-----BEGIN CERTIFICATE-----
    ChM0WE1MIFNlY3VyaXR5IExpYnJhcnkgKGh0dHA6Ly93d3cuYWxla3NleS5jb20v
    eG1sc2VjKTEZMBcGA1UECxMQUm9vdCBDZXJ0aWZpY2F0ZTEWMBQGA1UEAxMNQWxl
    a3NleSBTYW5pbjEhMB8GCSqGSIb3DQEJARYSeG1sc2VjQGFsZWtzZXkuY29tMB4X
    DTAzMDMzMTA0MDIyMloXDTEzMDMyODA0MDIyMlowgb8xCzAJBgNVBAYTAlVTMRMw
    EQYDVQQIEwpDYWxpZm9ybmlhMT0wOwYDVQQKEzRYTUwgU2VjdXJpdHkgTGlicmFy
    eSAoaHR0cDovL3d3dy5hbGVrc2V5LmNvbS94bWxzZWMpMSEwHwYDVQQLExhFeGFt
    cGxlcyBSU0EgQ2VydGlmaWNhdGUxFjAUBgNVBAMTDUFsZWtzZXkgU2FuaW4xITAf
    BgkqhkiG9w0BCQEWEnhtbHNlY0BhbGVrc2V5LmNvbTCCASIwDQYJKoZIhvcNAQEB
    BQADggEPADCCAQoCggEBAJe4/rQ/gzV4FokE7CthjL/EXwCBSkXm2c3p4jyXO0Wt
    quaNC3dxBwFPfPl94hmq3ZFZ9PHPPbp4RpYRnLZbRjlzVSOq954AXOXpSew7nD+E
    mTqQrd9+ZIbGJnLOMQh5fhMVuOW/1lYCjWAhTCcYZPv7VXD2M70vVXDVXn6ZrqTg
    w3dcTZBoihHftE8=
    -----END CERTIFICATE-----</certificate>
        <key>-----BEGIN PRIVATE KEY-----
    MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAMtnxavY/9jvytQlDI/fiZ3o+j3b
    nDhE0woQVqzuLT2brUUB3bSdvLsupV/wISLFRSTaKenZ2Bgi3mTrBjEdZs/qipsw4phrwVPaUp/q
    Gz1XreE6RK4LBjlbQS+pIkLg3eem9whCXgmRZJFhX3tDIL75oWYOFFEXZaAjmQUNpj3BAgMBAAEC
    trO9JAvQH/3z0B53tofvgA8U00kndI8MoiRbN/eUiSRFAN2DRnVYKS4ZCcVBOOBwQ7eEcktrn9M2
    VidjtAafdNADzwD+tJohsWECQQD2eT4JNTcI+xkQu53qODXoeEzusosXfmC5/+mwXMJp/3kv/jmO
    GwuLdlvD/e0R0imZ+GHNiw6MyfEWhiepYmGtAkEA00RjBRUex0Z5oTz/WIc6gyqkxMPAwxNOrXxu
    J1tokgITO/DCCJ1Xs8edDeq3cps2CpeHwIHC1o+GaVyG4BR3goNn6BUaK6qvWA0CQBrpLyPKmO0R
    URT0zCHet9lVaT+XH8q5fuAiZXncCOA7f37Se0hojqYEXvCRFeTNi9Fconl9pICelvIpDSL5cvEC
    SGsMB351VonwYzr49uSNdeGINw8bUhN/osdj6v8gxjmhbUAW5QJBALeuyY3BK9+0igyPVfN8qqgy
    gYEAkHapa/346EiW08lkfKKVCPQ5Fsns0AIBqToldTjMJN92VnaW0frd2kus5NCVmC5nh17zOcWg
    QEtAy9gMuRO46tJwXrN+hurJdicrbushw0GZA/TukgUnPPpldgxpkH6JFgbsl8XdrfAbMXuiAex/
    V3wdTItQ6So=
    -----END PRIVATE KEY-----</key>
      </ec2_credentials>
    </provider_credentials>


*Provider definition:*

The provider definition for EC2 is simply the name of the region.



# Rackspace

*Credentials:*

    <provider_credentials>
      <rackspace_credentials>
        <account_number>123456</account_number>
        <username>rackspaceuser</username>
        <password>changeme</password>
      </rackspace_credentials>
    </provider_credentials>


*Provider definition:*

The provider definition for Rackspace is simply the name of the region.



# OpenStack

*Credentials:*

    <provider_credentials>
      <openstack_credentials>
        <username>admin</username>
        <tenant>admin</tenant>
        <password>cloudpass</password>
        <strategy>keystone</strategy>
        <auth_url>http://openstack:5000/v2.0</auth_url>
      </openstack_credentials>
    </provider_credentials>


*Provider definition:*

    { 
      "glance-host": "openstack",
      "glance-port": 9292 
    }



# RHEVM

*Credentials:*

    <provider_credentials>
      <rhevm_credentials>
        <username>admin@internal</username>
        <password>changeme</password>
      </rhevm_credentials>
    </provider_credentials>


*Provider definition:*

    {
      "api-url":   "https://10.16.120.230:8443/api",
      "username":  "admin@internal",
      "password":  "changeme",
      "nfs-path":  "/home/rhev/me_expt",
      "nfs-dir":   "/mnt/rhevm",
      "nfs-host":  "qeblade26.rhq.lab.eng.bos.redhat.com",
      "cluster":   "_any_",
      "timeout":   1800
    }



# vSphere

*Credentials:*

    <provider_credentials>
      <vsphere_credentials>
        <username>admin@internal</username>
        <password>changeme</password>
      </vsphere_credentials>
    </provider_credentials>


*Provider definition:*

    {
      "api-url":   "10.16.120.224",
      "username":  "Administrator",
      "password":     "changeme",
      "datastore":    "datastore1",
      "compute_resource":  "10.16.120.53",
      "network_name": "VM Network"
    }



