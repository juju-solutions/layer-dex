
build:
		charm build -r

deploy: build
	juju deploy ${JUJU_REPOSITORY}/builds/dex

lint:
	/usr/bin/python3 -m flake8 reactive lib

upgrade: build
	juju upgrade-charm dex --path=${JUJU_REPOSITORY}/builds/dex

force: build
	juju upgrade-charm dex --path=${JUJU_REPOSITORY}/builds/dex --force-units

clean:
	rm -rf .tox
	rm -f .coverage
	rm -rf ./tmp

clean-all:
	rm -rf ${JUJU_REPOSITORY}/builds/dex

# This is a best effort method to deploy the test formation. This presumes
# unit 1 is always the kubernetes-master.
test-formation: build
	juju deploy kubernetes-core
	juju deploy ${JUJU_REPOSITORY}/builds/dex --to 0
	juju add-relation dex easyrsa
