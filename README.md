# Overview

This charm provides [Dex][https://github.com/coreos/dex]. Add a description
here of what the service itself actually does.

# Usage

Step by step instructions on using the charm:

```
juju deploy cs:~containers/easyrsa
juju deploy cs:~containers/dex
juju add-relation dex easyrsa
juju add-relation dex kubernetes-master
```

## Scale out Usage

If the charm has any recommendations for running at scale, outline them in
examples here. For example if you have a memcached relation that improves
performance, mention it here.

## Known Limitations and Issues


## Upstream Project Name

  - Upstream website
  - Upstream bug tracker
  - Upstream mailing list or contact information

[service]: http://example.com
