
build:
		charm build -r --no-local-layers

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
